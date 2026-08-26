"""export_entity and purge_entity (SPEC 12)."""
import json
from io import StringIO

import pytest
from django.core.management import CommandError, call_command
from django.utils import timezone

from core import models


@pytest.fixture
def populated(entity):
    source = models.DataSource.objects.create(
        entity=entity,
        kind=models.DataSource.Kind.GMAIL,
        credentials_enc=b"pretend-ciphertext",
    )
    models.Event.objects.create(
        entity=entity,
        source=source,
        type="email.received",
        dedup_key="msg-1",
        payload={"subject": "hi"},
        occurred_at=timezone.now(),
    )
    models.MemoryItem.objects.create(
        entity=entity,
        kind=models.MemoryItem.Kind.IDENTITY,
        content="lives in Istanbul",
        provenance="telegram:onboarding",
        confidence=0.9,
    )
    return entity


class TestExport:
    def run(self, entity_id):
        out = StringIO()
        call_command("export_entity", entity_id, stdout=out)
        return json.loads(out.getvalue())

    def test_exports_records_and_counts(self, populated):
        payload = self.run(populated.pk)
        assert payload["entity"]["name"] == populated.name
        assert payload["counts"]["events"] == 1
        assert payload["counts"]["memory_items"] == 1
        assert payload["records"]["events"][0]["dedup_key"] == "msg-1"

    def test_never_exports_credentials(self, populated):
        """Export is a data right, not a key leak."""
        payload = self.run(populated.pk)
        source = payload["records"]["data_sources"][0]
        assert "credentials_enc" not in source
        assert source["credentials_enc_present"] is True
        assert "pretend-ciphertext" not in json.dumps(payload)

    def test_omits_derived_embeddings(self, populated):
        assert "embedding" not in self.run(populated.pk)["records"]["memory_items"][0]

    def test_unknown_entity_fails(self, db):
        with pytest.raises(CommandError, match="not found"):
            self.run(9999)

    def test_writes_to_file(self, populated, tmp_path):
        target = tmp_path / "export.json"
        call_command("export_entity", populated.pk, "--output", str(target), stderr=StringIO())
        assert json.loads(target.read_text())["counts"]["events"] == 1


class TestPurge:
    def test_refuses_without_confirmation(self, populated):
        with pytest.raises(CommandError, match="--yes"):
            call_command("purge_entity", populated.pk)
        assert models.Entity.objects.filter(pk=populated.pk).exists()
        assert models.Event.objects.count() == 1

    def test_deletes_entity_and_attached_rows(self, populated):
        call_command("purge_entity", populated.pk, "--yes", stdout=StringIO())
        assert not models.Entity.objects.filter(pk=populated.pk).exists()
        assert models.Event.objects.count() == 0
        assert models.MemoryItem.objects.count() == 0
        assert models.DataSource.objects.count() == 0

    def test_leaves_other_entities_alone(self, populated, company):
        models.Event.objects.create(
            entity=company,
            type="order.created",
            dedup_key="order-1",
            payload={},
            occurred_at=timezone.now(),
        )
        call_command("purge_entity", populated.pk, "--yes", stdout=StringIO())
        assert models.Entity.objects.filter(pk=company.pk).exists()
        assert models.Event.objects.filter(entity=company).count() == 1

    def test_unknown_entity_fails(self, db):
        with pytest.raises(CommandError, match="not found"):
            call_command("purge_entity", 9999, "--yes")
