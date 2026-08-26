"""LLMService (SPEC 5, 8, 10).

Every model call in the system goes through here. The service owns three
things nothing else is allowed to duplicate: tier routing, cost accounting,
and the daily budget ceiling.
"""
from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

import yaml
from django.conf import settings as django_settings
from django.db import connection, transaction
from django.db.models import F, Sum
from django.utils import timezone

from core.models import Entity, LLMUsage
from core.services import llm_backends
from core.services.settings_schema import parse as parse_settings

TIERS_PATH = Path(django_settings.BASE_DIR) / "config" / "llm_tiers.yaml"

# Reservations are deliberately pessimistic: characters divided by three
# over-counts input tokens, and output is charged at the full max_tokens. The
# ledger is corrected with real usage once the call returns, so the error only
# ever makes the guard stricter, never looser.
CHARS_PER_TOKEN_ESTIMATE = 3
TOKENS_PER_MILLION = Decimal(1_000_000)


class LLMError(RuntimeError):
    """Base class for LLMService failures."""


class BudgetExceeded(LLMError):
    """The entity's daily spend ceiling would be crossed by this call."""


class TierNotConfigured(LLMError):
    """The requested tier is missing from config/llm_tiers.yaml."""


class TierCallCapExceeded(LLMError):
    """The tier's daily call cap is spent (SPEC 10: frontier is capped)."""


@dataclass(frozen=True)
class TierConfig:
    name: str
    backend: str
    model: str
    input_usd_per_mtok: Decimal
    output_usd_per_mtok: Decimal
    max_tokens: int
    timeout_seconds: float
    daily_call_cap: int | None = None
    dimensions: int | None = None

    def cost(self, input_tokens: int, output_tokens: int) -> Decimal:
        return (
            self.input_usd_per_mtok * Decimal(input_tokens)
            + self.output_usd_per_mtok * Decimal(output_tokens)
        ) / TOKENS_PER_MILLION


@dataclass
class LLMResponse:
    text: str
    tier: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal


@dataclass
class EmbeddingResponse:
    vectors: list[list[float]]
    tier: str
    model: str
    input_tokens: int
    cost_usd: Decimal


@lru_cache(maxsize=1)
def _load_tiers(path: str, mtime: float) -> dict[str, TierConfig]:
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    defaults = raw.get("defaults") or {}
    tiers: dict[str, TierConfig] = {}
    for name, spec in (raw.get("tiers") or {}).items():
        tiers[name] = TierConfig(
            name=name,
            backend=spec["backend"],
            model=spec["model"],
            input_usd_per_mtok=Decimal(str(spec.get("input_usd_per_mtok", 0))),
            output_usd_per_mtok=Decimal(str(spec.get("output_usd_per_mtok", 0))),
            max_tokens=int(spec.get("max_tokens", defaults.get("max_tokens", 4096))),
            timeout_seconds=float(
                spec.get("timeout_seconds", defaults.get("timeout_seconds", 120))
            ),
            daily_call_cap=spec.get("daily_call_cap"),
            dimensions=spec.get("dimensions"),
        )
    return tiers


def load_tiers(path: Path | None = None) -> dict[str, TierConfig]:
    """Read the routing table, reloading whenever the file changes on disk."""
    target = Path(path or TIERS_PATH)
    return _load_tiers(str(target), target.stat().st_mtime)


class LLMService:
    def __init__(self, entity: Entity, tiers_path: Path | None = None):
        self.entity = entity
        self._tiers_path = tiers_path

    # -- configuration ---------------------------------------------------

    def tier(self, name: str) -> TierConfig:
        tiers = load_tiers(self._tiers_path)
        if name not in tiers:
            raise TierNotConfigured(f"tier '{name}' is not defined in llm_tiers.yaml")
        return tiers[name]

    @property
    def daily_budget(self) -> Decimal:
        return Decimal(str(parse_settings(self.entity.settings).daily_budget_usd))

    def spent_today(self, day: dt.date | None = None) -> Decimal:
        day = day or timezone.localdate()
        total = LLMUsage.objects.filter(entity=self.entity, date=day).aggregate(
            total=Sum("cost_usd")
        )["total"]
        return Decimal(total or 0)

    def remaining_budget(self, day: dt.date | None = None) -> Decimal:
        return self.daily_budget - self.spent_today(day)

    # -- calling ---------------------------------------------------------

    def call(
        self,
        tier: str,
        messages: list[dict],
        purpose: str,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Run a completion. Raises BudgetExceeded rather than overspending."""
        config = self.tier(tier)
        purpose = self._require_purpose(purpose)
        limit = max_tokens or config.max_tokens
        estimate = self._estimate_cost(config, messages, limit)

        usage = self._reserve(config, purpose, estimate)
        try:
            result = llm_backends.get_backend(config.backend).complete(
                model=config.model,
                messages=messages,
                max_tokens=limit,
                timeout=config.timeout_seconds,
            )
        except Exception:
            self._release(usage, estimate)
            raise

        actual = config.cost(result.input_tokens, result.output_tokens)
        self._settle(usage, estimate, actual, result.input_tokens, result.output_tokens)
        return LLMResponse(
            text=result.text,
            tier=tier,
            model=config.model,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=actual,
        )

    def embed(self, texts: list[str], purpose: str, tier: str = "TIER_EMBED") -> EmbeddingResponse:
        config = self.tier(tier)
        purpose = self._require_purpose(purpose)
        estimated_tokens = sum(
            max(1, math.ceil(len(text) / CHARS_PER_TOKEN_ESTIMATE)) for text in texts
        )
        estimate = config.cost(estimated_tokens, 0)

        usage = self._reserve(config, purpose, estimate)
        try:
            result = llm_backends.get_backend(config.backend).embed(
                model=config.model, texts=texts, timeout=config.timeout_seconds
            )
        except Exception:
            self._release(usage, estimate)
            raise

        actual = config.cost(result.input_tokens, 0)
        self._settle(usage, estimate, actual, result.input_tokens, 0)
        return EmbeddingResponse(
            vectors=result.vectors,
            tier=tier,
            model=config.model,
            input_tokens=result.input_tokens,
            cost_usd=actual,
        )

    def try_call(self, tier: str, messages: list[dict], purpose: str, **kwargs):
        """Budget-aware variant: returns None instead of raising.

        This is the primitive behind degraded mode (SPEC 8) - a caller that must
        still produce something when the ceiling is reached, such as the
        briefing going out without its synthesis rather than not going out.
        """
        try:
            return self.call(tier, messages, purpose, **kwargs)
        except (BudgetExceeded, TierCallCapExceeded):
            return None

    # -- accounting ------------------------------------------------------

    @staticmethod
    def _require_purpose(purpose: str) -> str:
        purpose = (purpose or "").strip()
        if not purpose:
            # SPEC 10: without a purpose the daily report cannot break spend down.
            raise ValueError("purpose is required for every LLM call")
        return purpose

    def _estimate_cost(self, config: TierConfig, messages: list[dict], max_tokens: int) -> Decimal:
        characters = sum(len(str(message.get("content", ""))) for message in messages)
        input_tokens = max(1, math.ceil(characters / CHARS_PER_TOKEN_ESTIMATE))
        return config.cost(input_tokens, max_tokens)

    def _lock_day(self, day: dt.date) -> None:
        """Serialize check-and-reserve for this entity and day.

        A transaction-scoped advisory lock keeps two concurrent calls from both
        reading the same spend and both deciding there is room.
        """
        with connection.cursor() as cursor:
            cursor.execute(
                "SELECT pg_advisory_xact_lock(%s, %s)",
                [self.entity.pk, day.toordinal()],
            )

    def _reserve(self, config: TierConfig, purpose: str, estimate: Decimal) -> LLMUsage:
        day = timezone.localdate()
        with transaction.atomic():
            self._lock_day(day)

            if config.daily_call_cap is not None:
                calls_today = (
                    LLMUsage.objects.filter(
                        entity=self.entity, date=day, tier=config.name
                    ).aggregate(total=Sum("calls"))["total"]
                    or 0
                )
                if calls_today >= config.daily_call_cap:
                    raise TierCallCapExceeded(
                        f"{config.name} is capped at {config.daily_call_cap} calls per day"
                    )

            spent = self.spent_today(day)
            budget = self.daily_budget
            if spent + estimate > budget:
                raise BudgetExceeded(
                    f"daily budget {budget} USD would be exceeded: "
                    f"{spent} spent, {estimate} estimated for this call"
                )

            usage, _ = LLMUsage.objects.get_or_create(
                entity=self.entity, date=day, tier=config.name, purpose=purpose
            )
            LLMUsage.objects.filter(pk=usage.pk).update(
                cost_usd=F("cost_usd") + estimate, calls=F("calls") + 1
            )
            usage.refresh_from_db()
            return usage

    @staticmethod
    def _release(usage: LLMUsage, estimate: Decimal) -> None:
        """A failed call reserved budget it never spent - give it back."""
        LLMUsage.objects.filter(pk=usage.pk).update(
            cost_usd=F("cost_usd") - estimate, calls=F("calls") - 1
        )

    @staticmethod
    def _settle(
        usage: LLMUsage,
        estimate: Decimal,
        actual: Decimal,
        input_tokens: int,
        output_tokens: int,
    ) -> None:
        LLMUsage.objects.filter(pk=usage.pk).update(
            cost_usd=F("cost_usd") - estimate + actual,
            input_tokens=F("input_tokens") + input_tokens,
            output_tokens=F("output_tokens") + output_tokens,
        )
