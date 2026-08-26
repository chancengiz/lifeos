"""Irreversibly delete one entity and everything attached to it (SPEC 12)."""
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core import models


class Command(BaseCommand):
    help = "Permanently delete an entity and all of its data. Cannot be undone."

    def add_arguments(self, parser):
        parser.add_argument("entity_id", type=int)
        parser.add_argument(
            "--yes",
            action="store_true",
            help="Confirm the deletion. Without it nothing is removed.",
        )

    def handle(self, *args, **options):
        entity_id = options["entity_id"]
        try:
            entity = models.Entity.objects.get(pk=entity_id)
        except models.Entity.DoesNotExist as exc:
            raise CommandError(f"entity {entity_id} not found") from exc

        if not options["yes"]:
            raise CommandError(
                f"refusing to delete '{entity.name}' (id={entity_id}) without --yes"
            )

        with transaction.atomic():
            name = entity.name
            _, per_model = entity.delete()

        total = sum(per_model.values())
        self.stdout.write(f"purged entity '{name}' (id={entity_id}): {total} rows")
        for label, count in sorted(per_model.items()):
            self.stdout.write(f"  {label}: {count}")
