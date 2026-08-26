"""Export every stored record for one entity as JSON (SPEC 12).

Secrets are never exported: DataSource.credentials_enc is replaced by a
presence flag, and embeddings are omitted as derived data.
"""
import json
import sys

from django.core.management.base import BaseCommand, CommandError
from django.core.serializers.json import DjangoJSONEncoder

from core import models

# (label, model, field pointing at Entity)
EXPORTED = [
    ("entity_members", models.EntityMember, "entity"),
    ("data_sources", models.DataSource, "entity"),
    ("events", models.Event, "entity"),
    ("memory_items", models.MemoryItem, "entity"),
    ("exposures", models.ExposureItem, "entity"),
    ("interests", models.InterestNode, "entity"),
    ("stances", models.Stance, "entity"),
    ("research_tasks", models.ResearchTask, "entity"),
    ("research_steps", models.ResearchStep, "task__entity"),
    ("source_documents", models.SourceDocument, "entity"),
    ("impact_findings", models.ImpactFinding, "entity"),
    ("agent_identities", models.AgentIdentity, "entity"),
    ("share_contracts", models.ShareContract, "entity"),
    ("mesh_conversations", models.MeshConversation, "entity"),
    ("mesh_messages", models.MeshMessage, "conversation__entity"),
    ("proposed_actions", models.ProposedAction, "entity"),
    ("action_policies", models.ActionPolicy, "entity"),
    ("exploration_ledger", models.ExplorationLedger, "entity"),
    ("briefings", models.Briefing, "entity"),
    ("feedback_signals", models.FeedbackSignal, "entity"),
    ("audit_logs", models.AuditLog, "entity"),
    ("llm_usage", models.LLMUsage, "entity"),
]

SECRET_FIELDS = {"credentials_enc"}
DERIVED_FIELDS = {"embedding"}


def _row(instance) -> dict:
    data = {}
    for field in instance._meta.fields:
        name = field.name
        if name in DERIVED_FIELDS:
            continue
        if name in SECRET_FIELDS:
            data[f"{name}_present"] = getattr(instance, field.attname) is not None
            continue
        data[name] = getattr(instance, field.attname)
    for field in instance._meta.many_to_many:
        data[field.name] = list(
            getattr(instance, field.name).values_list("pk", flat=True)
        )
    return data


class Command(BaseCommand):
    help = "Export all data for one entity as JSON."

    def add_arguments(self, parser):
        parser.add_argument("entity_id", type=int)
        parser.add_argument("--output", "-o", default="-", help="File path, or - for stdout.")

    def handle(self, *args, **options):
        entity_id = options["entity_id"]
        try:
            entity = models.Entity.objects.get(pk=entity_id)
        except models.Entity.DoesNotExist as exc:
            raise CommandError(f"entity {entity_id} not found") from exc

        payload = {
            "entity": _row(entity),
            "counts": {},
            "records": {},
        }
        for label, model, path in EXPORTED:
            rows = [_row(obj) for obj in model.objects.filter(**{path: entity})]
            payload["records"][label] = rows
            payload["counts"][label] = len(rows)

        text = json.dumps(payload, cls=DjangoJSONEncoder, ensure_ascii=False, indent=2)
        target = options["output"]
        if target == "-":
            self.stdout.write(text)
        else:
            with open(target, "w", encoding="utf-8") as handle:
                handle.write(text)
            self.stderr.write(f"wrote {target}")
