import pytest

from core import models


@pytest.fixture
def entity(db):
    return models.Entity.objects.create(kind=models.Entity.Kind.PERSON, name="Test Person")


@pytest.fixture
def company(db):
    return models.Entity.objects.create(kind=models.Entity.Kind.COMPANY, name="Test Company")
