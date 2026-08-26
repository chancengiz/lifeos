"""The skeleton itself: migrations clean, registry empty, admin complete."""
from io import StringIO

import pytest
from django.contrib import admin
from django.core.management import call_command

from config.module_registry import ENABLED_MODULES
from core import models


def test_no_missing_migrations(db):
    """makemigrations --check must find nothing to add."""
    call_command("makemigrations", "--check", "--dry-run", stdout=StringIO())


def test_module_registry_starts_empty():
    """SPEC 4: a new module is a folder plus one line here, nothing else."""
    assert ENABLED_MODULES == []


@pytest.mark.parametrize(
    "model",
    [m for m in models.__dict__.values() if isinstance(m, type) and issubclass(m, models.models.Model)
     and m.__module__ == "core.models"],
)
def test_every_model_is_registered_in_admin(model):
    assert model in admin.site._registry
