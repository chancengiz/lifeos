"""Model-level guarantees the rest of the system is allowed to assume."""
import datetime as dt

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from core import models


def make_event(entity, **overrides):
    data = dict(
        entity=entity,
        type="email.received",
        dedup_key="gmail-msg-1",
        payload={"subject": "hi"},
        occurred_at=timezone.now(),
    )
    data.update(overrides)
    return models.Event.objects.create(**data)


class TestEventDedup:
    """B1: the contract says a module never emits the same event twice."""

    def test_same_triple_is_rejected(self, entity):
        make_event(entity)
        with pytest.raises(IntegrityError):
            make_event(entity)

    def test_different_type_is_allowed(self, entity):
        make_event(entity)
        make_event(entity, type="email.archived")
        assert models.Event.objects.count() == 2

    def test_different_entity_is_allowed(self, entity, company):
        make_event(entity)
        make_event(company)
        assert models.Event.objects.count() == 2

    def test_blank_dedup_key_is_rejected(self, entity):
        with pytest.raises(IntegrityError):
            make_event(entity, dedup_key="")


class TestProposedActionDedup:
    """B1 again: the same proposal must not reach the owner twice."""

    def make(self, entity, **overrides):
        data = dict(
            entity=entity,
            module="world_impact",
            action_type="exposure.update",
            dedup_key="exposure-7",
            payload={},
        )
        data.update(overrides)
        return models.ProposedAction.objects.create(**data)

    def test_duplicate_is_rejected(self, entity):
        self.make(entity)
        with pytest.raises(IntegrityError):
            self.make(entity)

    def test_blank_dedup_key_is_rejected(self, entity):
        with pytest.raises(IntegrityError):
            self.make(entity, dedup_key="")


class TestMemoryItem:
    def make(self, entity, **overrides):
        data = dict(
            entity=entity,
            kind=models.MemoryItem.Kind.SEMANTIC,
            content="prefers morning meetings",
            provenance="telegram:onboarding",
            confidence=0.8,
        )
        data.update(overrides)
        return models.MemoryItem.objects.create(**data)

    def test_blank_provenance_is_rejected(self, entity):
        """SPEC 5: a memory with no source cannot be trusted, so it cannot be stored."""
        with pytest.raises(IntegrityError):
            self.make(entity, provenance="")

    def test_confidence_outside_range_is_rejected(self, entity):
        with pytest.raises(IntegrityError):
            self.make(entity, confidence=1.4)

    def test_defaults_to_exploit_lane(self, entity):
        item = self.make(entity)
        assert item.origin_lane == models.Lane.EXPLOIT
        assert item.decay_exempt_until is None
        assert item.promoted_at is None

    def test_exploration_item_can_carry_decay_shield(self, entity):
        """SPEC 7: exploration needs time to prove itself before decay applies."""
        until = timezone.now() + dt.timedelta(days=60)
        item = self.make(entity, origin_lane=models.Lane.RANDOM, decay_exempt_until=until)
        item.refresh_from_db()
        assert item.origin_lane == models.Lane.RANDOM
        assert item.decay_exempt_until is not None


class TestImpactFinding:
    """SPEC 0/7: no claim without an exposure to hang it on."""

    def test_exposure_is_required(self, entity):
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                models.ImpactFinding.objects.create(
                    entity=entity,
                    exposure=None,
                    claim="the world moved",
                    direction=models.ImpactFinding.Direction.RISK,
                    magnitude=models.ImpactFinding.Magnitude.LOW,
                    confidence=0.5,
                )

    def test_blank_claim_is_rejected(self, entity):
        exposure = models.ExposureItem.objects.create(
            entity=entity, kind=models.ExposureItem.Kind.CURRENCY, label="TRY/USD"
        )
        with pytest.raises(IntegrityError):
            models.ImpactFinding.objects.create(
                entity=entity,
                exposure=exposure,
                claim="",
                direction=models.ImpactFinding.Direction.RISK,
                magnitude=models.ImpactFinding.Magnitude.LOW,
                confidence=0.5,
            )

    def test_finding_links_exposure_and_evidence(self, entity):
        exposure = models.ExposureItem.objects.create(
            entity=entity, kind=models.ExposureItem.Kind.CURRENCY, label="TRY/USD"
        )
        doc = models.SourceDocument.objects.create(
            entity=entity, url="https://example.org/a", text="...", content_hash="h1"
        )
        finding = models.ImpactFinding.objects.create(
            entity=entity,
            exposure=exposure,
            claim="ad spend in USD gets more expensive",
            direction=models.ImpactFinding.Direction.RISK,
            magnitude=models.ImpactFinding.Magnitude.MEDIUM,
            confidence=0.6,
        )
        finding.evidence.add(doc)
        assert finding.evidence.count() == 1


class TestFeedbackSignal:
    def test_second_tap_on_same_target_is_rejected(self, entity):
        """K1: a double thumbs-up updates one row instead of creating two."""
        models.FeedbackSignal.objects.create(
            entity=entity,
            target_type=models.FeedbackSignal.TargetType.BRIEFING_ITEM,
            target_ref="2026-08-26:world_impact:0",
            signal=models.FeedbackSignal.Signal.UP,
        )
        with pytest.raises(IntegrityError):
            models.FeedbackSignal.objects.create(
                entity=entity,
                target_type=models.FeedbackSignal.TargetType.BRIEFING_ITEM,
                target_ref="2026-08-26:world_impact:0",
                signal=models.FeedbackSignal.Signal.DOWN,
            )


class TestUniqueness:
    def test_source_document_dedups_by_content_hash(self, entity):
        models.SourceDocument.objects.create(
            entity=entity, url="https://example.org/a", text="x", content_hash="same"
        )
        with pytest.raises(IntegrityError):
            models.SourceDocument.objects.create(
                entity=entity, url="https://example.org/b", text="x", content_hash="same"
            )

    def test_one_briefing_per_entity_per_day(self, entity):
        models.Briefing.objects.create(entity=entity, date=dt.date(2026, 8, 26))
        with pytest.raises(IntegrityError):
            models.Briefing.objects.create(entity=entity, date=dt.date(2026, 8, 26))

    def test_research_step_index_is_unique_per_task(self, entity):
        task = models.ResearchTask.objects.create(entity=entity, goal="check FX")
        models.ResearchStep.objects.create(task=task, index=0, tool="web_search")
        with pytest.raises(IntegrityError):
            models.ResearchStep.objects.create(task=task, index=0, tool="web_fetch")


class TestMesh:
    def test_share_contract_starts_unapproved(self, entity):
        """SPEC 6: a contract is not usable until a human approved it."""
        peer = models.AgentIdentity.objects.create(display_name="Peer")
        contract = models.ShareContract.objects.create(
            entity=entity, peer=peer, purpose="schedule"
        )
        assert contract.approved_by_user_at is None
        assert contract.allowed_fields == []

    def test_message_records_what_was_withheld(self, entity):
        peer = models.AgentIdentity.objects.create(display_name="Peer")
        convo = models.MeshConversation.objects.create(
            entity=entity, peer=peer, topic="meeting", purpose="schedule"
        )
        message = models.MeshMessage.objects.create(
            conversation=convo,
            direction=models.MeshMessage.Direction.OUT,
            kind="propose",
            body={"free_busy": ["2026-08-27T09:00Z"]},
            redaction_note={"dropped": ["calendar.title"]},
        )
        assert message.redaction_note["dropped"] == ["calendar.title"]
