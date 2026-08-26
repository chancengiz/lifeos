"""Validation for Entity.settings (SPEC 3.1).

Config changes must not require code changes, which only holds if the config
has a shape. This module is that shape.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field, fields


class SettingsError(ValueError):
    """Raised when Entity.settings does not satisfy the schema."""


@dataclass
class ExplorationSettings:
    """SPEC 7. Lane shares are fractions of the total research budget."""

    enabled: bool = True
    adjacent: float = 0.07
    counter: float = 0.05
    random: float = 0.03
    # A floor, not a ceiling: a busy day may not push exploration to zero.
    min_briefing_items: int = 1
    decay_exempt_days: int = 60

    def total(self) -> float:
        return self.adjacent + self.counter + self.random

    def validate(self) -> None:
        for name in ("adjacent", "counter", "random"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise SettingsError(f"exploration.{name} must be within 0.0-1.0")
        if self.total() > 1.0:
            raise SettingsError("exploration lane shares must not exceed 1.0 in total")
        if self.enabled and self.min_briefing_items < 1:
            raise SettingsError("exploration.min_briefing_items must be at least 1")
        if self.decay_exempt_days < 0:
            raise SettingsError("exploration.decay_exempt_days must not be negative")


@dataclass
class MeshSettings:
    """SPEC 6."""

    enabled: bool = False
    # Share of peer contacts deliberately outside the owner's own field.
    unrelated_peer_ratio: float = 0.15
    max_open_conversations: int = 5

    def validate(self) -> None:
        if not 0.0 <= self.unrelated_peer_ratio <= 1.0:
            raise SettingsError("mesh.unrelated_peer_ratio must be within 0.0-1.0")
        if self.max_open_conversations < 1:
            raise SettingsError("mesh.max_open_conversations must be at least 1")


@dataclass
class EntitySettings:
    daily_budget_usd: float = 1.50
    briefing_hour: int = 8
    telegram_chat_id: int | None = None
    rss_feeds: list[str] = field(default_factory=list)
    agent_daily_task_cap: int = 12
    exploration: ExplorationSettings = field(default_factory=ExplorationSettings)
    mesh: MeshSettings = field(default_factory=MeshSettings)

    def validate(self) -> None:
        if self.daily_budget_usd <= 0:
            raise SettingsError("daily_budget_usd must be positive")
        if not 0 <= self.briefing_hour <= 23:
            raise SettingsError("briefing_hour must be within 0-23")
        if self.agent_daily_task_cap < 0:
            raise SettingsError("agent_daily_task_cap must not be negative")
        if not isinstance(self.rss_feeds, list):
            raise SettingsError("rss_feeds must be a list")
        self.exploration.validate()
        self.mesh.validate()

    def to_dict(self) -> dict:
        return asdict(self)


_NESTED = {"exploration": ExplorationSettings, "mesh": MeshSettings}


def parse(raw: dict | None) -> EntitySettings:
    """Build validated settings from stored JSON, rejecting unknown keys."""
    raw = dict(raw or {})
    known = {f.name for f in fields(EntitySettings)}
    unknown = set(raw) - known
    if unknown:
        raise SettingsError(f"unknown settings key(s): {', '.join(sorted(unknown))}")

    kwargs: dict = {}
    for key, value in raw.items():
        nested_cls = _NESTED.get(key)
        if nested_cls is None:
            kwargs[key] = value
            continue
        if not isinstance(value, dict):
            raise SettingsError(f"{key} must be an object")
        nested_known = {f.name for f in fields(nested_cls)}
        nested_unknown = set(value) - nested_known
        if nested_unknown:
            raise SettingsError(
                f"unknown settings key(s): {', '.join(f'{key}.{k}' for k in sorted(nested_unknown))}"
            )
        kwargs[key] = nested_cls(**value)

    settings = EntitySettings(**kwargs)
    settings.validate()
    return settings
