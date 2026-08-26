"""LLMService: tier routing, cost accounting, budget ceiling (SPEC 8, 10)."""
import time
from decimal import Decimal

import pytest
from django.utils import timezone

from core.models import LLMUsage
from core.services import llm_backends
from core.services.llm import (
    BudgetExceeded,
    LLMService,
    TierCallCapExceeded,
    TierNotConfigured,
    load_tiers,
)
from core.services.llm_backends import CompletionResult, EmbeddingResult


class FakeBackend:
    """Stands in for every provider. Records what it was asked for."""

    def __init__(self, input_tokens=100, output_tokens=50, fail=False, delay=0.0):
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.fail = fail
        self.delay = delay
        self.calls = []

    def complete(self, model, messages, max_tokens, timeout):
        self.calls.append({"model": model, "messages": messages, "max_tokens": max_tokens})
        if self.delay:
            time.sleep(self.delay)
        if self.fail:
            raise RuntimeError("provider is down")
        return CompletionResult(
            text="ok", input_tokens=self.input_tokens, output_tokens=self.output_tokens
        )

    def embed(self, model, texts, timeout):
        self.calls.append({"model": model, "texts": texts})
        if self.fail:
            raise RuntimeError("provider is down")
        return EmbeddingResult(vectors=[[0.0] * 4 for _ in texts], input_tokens=self.input_tokens)


@pytest.fixture
def backend():
    fake = FakeBackend()
    llm_backends.register_backend("anthropic", fake)
    llm_backends.register_backend("litellm", fake)
    yield fake
    llm_backends.reset_backends()


@pytest.fixture
def service(entity, backend):
    entity.settings = {"daily_budget_usd": 1.00}
    entity.save()
    return LLMService(entity)


MESSAGES = [{"role": "user", "content": "hello"}]


class TestTierTable:
    """SPEC 10: model names live in YAML, never in code."""

    def test_all_four_tiers_are_defined(self):
        assert set(load_tiers()) == {
            "TIER_EMBED",
            "TIER_SMALL",
            "TIER_MID",
            "TIER_FRONTIER",
        }

    def test_frontier_is_capped_per_day(self):
        assert load_tiers()["TIER_FRONTIER"].daily_call_cap == 3

    def test_embeddings_do_not_route_through_anthropic(self):
        """The Anthropic API has no embeddings endpoint."""
        assert load_tiers()["TIER_EMBED"].backend == "litellm"

    def test_embed_dimensions_match_the_stored_vector_size(self):
        from django.conf import settings

        assert load_tiers()["TIER_EMBED"].dimensions == settings.EMBEDDING_DIMENSIONS

    def test_unknown_tier_is_rejected(self, service):
        with pytest.raises(TierNotConfigured):
            service.call("TIER_IMAGINARY", MESSAGES, purpose="test")

    def test_cost_comes_from_the_table(self):
        tier = load_tiers()["TIER_MID"]
        # 1M input at $2 plus 1M output at $10.
        assert tier.cost(1_000_000, 1_000_000) == Decimal("12")


class TestCallAccounting:
    def test_call_returns_text_and_cost(self, service):
        response = service.call("TIER_SMALL", MESSAGES, purpose="triage")
        assert response.text == "ok"
        assert response.model == "claude-haiku-4-5"
        assert response.input_tokens == 100
        assert response.cost_usd > 0

    def test_usage_row_records_actual_tokens_not_the_estimate(self, service):
        service.call("TIER_SMALL", MESSAGES, purpose="triage")
        usage = LLMUsage.objects.get(entity=service.entity, tier="TIER_SMALL", purpose="triage")
        assert usage.input_tokens == 100
        assert usage.output_tokens == 50
        assert usage.calls == 1
        tier = load_tiers()["TIER_SMALL"]
        assert float(usage.cost_usd) == pytest.approx(float(tier.cost(100, 50)), abs=1e-4)

    def test_spend_accumulates_across_calls(self, service):
        service.call("TIER_SMALL", MESSAGES, purpose="triage")
        first = service.spent_today()
        service.call("TIER_SMALL", MESSAGES, purpose="triage")
        assert service.spent_today() > first
        assert LLMUsage.objects.count() == 1  # same tier and purpose, one row

    def test_purpose_is_required(self, service):
        """SPEC 10: spend has to be breakable down by purpose."""
        with pytest.raises(ValueError, match="purpose is required"):
            service.call("TIER_SMALL", MESSAGES, purpose="  ")

    def test_different_purposes_are_tracked_separately(self, service):
        service.call("TIER_SMALL", MESSAGES, purpose="triage")
        service.call("TIER_SMALL", MESSAGES, purpose="labelling")
        assert LLMUsage.objects.count() == 2


class TestBudgetCeiling:
    def test_call_is_refused_once_the_ceiling_is_reached(self, entity, backend):
        entity.settings = {"daily_budget_usd": 0.01}
        entity.save()
        service = LLMService(entity)
        LLMUsage.objects.create(
            entity=entity,
            date=timezone.localdate(),
            tier="TIER_FRONTIER",
            purpose="briefing",
            cost_usd=Decimal("0.01"),
            calls=1,
        )
        with pytest.raises(BudgetExceeded):
            service.call("TIER_MID", MESSAGES, purpose="analysis")
        assert backend.calls == []  # refused before reaching the provider

    def test_reservation_is_pessimistic_enough_to_cover_the_real_cost(self, service):
        """The estimate may overshoot, never undershoot - the guard stays strict."""
        tier = load_tiers()["TIER_SMALL"]
        estimate = service._estimate_cost(tier, MESSAGES, tier.max_tokens)
        response = service.call("TIER_SMALL", MESSAGES, purpose="triage")
        assert estimate >= response.cost_usd

    def test_failed_call_gives_its_reservation_back(self, service, backend):
        service.call("TIER_SMALL", MESSAGES, purpose="triage")
        settled = service.spent_today()

        backend.fail = True
        with pytest.raises(RuntimeError, match="provider is down"):
            service.call("TIER_SMALL", MESSAGES, purpose="triage")

        assert service.spent_today() == settled
        usage = LLMUsage.objects.get(entity=service.entity, tier="TIER_SMALL")
        assert usage.calls == 1

    def test_remaining_budget_shrinks_as_it_is_spent(self, service):
        before = service.remaining_budget()
        service.call("TIER_SMALL", MESSAGES, purpose="triage")
        assert service.remaining_budget() < before


class TestFrontierCallCap:
    """SPEC 10: at most three frontier calls per entity per day."""

    def test_fourth_call_is_refused(self, entity, backend):
        entity.settings = {"daily_budget_usd": 100.0}
        entity.save()
        service = LLMService(entity)
        for _ in range(3):
            service.call("TIER_FRONTIER", MESSAGES, purpose="briefing")
        with pytest.raises(TierCallCapExceeded):
            service.call("TIER_FRONTIER", MESSAGES, purpose="briefing")

    def test_cap_does_not_bleed_into_other_tiers(self, entity, backend):
        entity.settings = {"daily_budget_usd": 100.0}
        entity.save()
        service = LLMService(entity)
        for _ in range(3):
            service.call("TIER_FRONTIER", MESSAGES, purpose="briefing")
        assert service.call("TIER_MID", MESSAGES, purpose="analysis").text == "ok"


class TestDegradedMode:
    """SPEC 8: the one interface must not go silent when the ceiling is hit."""

    def test_try_call_returns_none_instead_of_raising_on_budget(self, entity, backend):
        entity.settings = {"daily_budget_usd": 0.01}
        entity.save()
        service = LLMService(entity)
        LLMUsage.objects.create(
            entity=entity,
            date=timezone.localdate(),
            tier="TIER_FRONTIER",
            purpose="briefing",
            cost_usd=Decimal("0.01"),
            calls=1,
        )
        assert service.try_call("TIER_MID", MESSAGES, purpose="analysis") is None

    def test_try_call_still_propagates_provider_failures(self, service, backend):
        """A provider outage is not a budget decision and must not be swallowed."""
        backend.fail = True
        with pytest.raises(RuntimeError):
            service.try_call("TIER_SMALL", MESSAGES, purpose="triage")


class TestEmbeddings:
    def test_embed_returns_one_vector_per_text(self, service):
        response = service.embed(["a", "b"], purpose="memory.write")
        assert len(response.vectors) == 2
        assert response.model == "text-embedding-3-small"

    def test_embed_is_billed(self, service):
        service.embed(["a"], purpose="memory.write")
        assert LLMUsage.objects.filter(tier="TIER_EMBED").exists()

    def test_anthropic_backend_refuses_embeddings_with_a_useful_message(self):
        backend = llm_backends.AnthropicBackend(client=object())
        with pytest.raises(llm_backends.BackendError, match="no embeddings endpoint"):
            backend.embed("whatever", ["a"], timeout=1)


class TestAnthropicBackend:
    def test_system_message_is_lifted_out_of_the_message_list(self):
        """The Anthropic API takes system as its own parameter, not a message."""
        captured = {}

        class FakeMessages:
            def create(self, **kwargs):
                captured.update(kwargs)
                return type(
                    "R",
                    (),
                    {
                        "content": [type("B", (), {"type": "text", "text": "hi"})()],
                        "usage": type("U", (), {"input_tokens": 5, "output_tokens": 2})(),
                    },
                )()

        class FakeClient:
            messages = FakeMessages()

            def with_options(self, **kwargs):
                return self

        backend = llm_backends.AnthropicBackend(client=FakeClient())
        result = backend.complete(
            model="claude-opus-5",
            messages=[
                {"role": "system", "content": "be terse"},
                {"role": "user", "content": "hello"},
            ],
            max_tokens=16,
            timeout=5,
        )
        assert captured["system"] == "be terse"
        assert captured["messages"] == [{"role": "user", "content": "hello"}]
        assert result.text == "hi"


class TestConcurrentReservation:
    """The ceiling has to hold when two workers reach it at the same moment.

    Celery runs several workers against one entity, so the check-and-reserve is
    serialized with a transaction-scoped advisory lock. Without it both callers
    read the same spend and both conclude there is room.
    """

    def test_only_one_of_two_simultaneous_calls_gets_through(
        self, transactional_db, entity
    ):
        import threading

        from django.db import connections

        # The winner stays in flight while the loser checks, which is the
        # interleaving the lock exists for.
        fake = FakeBackend(delay=0.5)
        llm_backends.register_backend("anthropic", fake)

        tier = load_tiers()["TIER_SMALL"]
        service = LLMService(entity)
        one_reservation = service._estimate_cost(tier, MESSAGES, tier.max_tokens)
        # Room for one reservation but nowhere near two.
        entity.settings = {"daily_budget_usd": float(one_reservation) * 1.5}
        entity.save()

        start = threading.Barrier(2)
        outcomes: list[str] = []
        lock = threading.Lock()

        def worker():
            try:
                start.wait(timeout=5)
                LLMService(entity).call("TIER_SMALL", MESSAGES, purpose="triage")
                result = "ok"
            except BudgetExceeded:
                result = "refused"
            finally:
                connections.close_all()
            with lock:
                outcomes.append(result)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=15)

        try:
            assert sorted(outcomes) == ["ok", "refused"]
            assert LLMService(entity).spent_today() <= one_reservation
            assert len(fake.calls) == 1
        finally:
            llm_backends.reset_backends()
