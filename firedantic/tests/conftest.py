import uuid
from unittest.mock import Mock

import google.auth.credentials
import pytest
from google.cloud import firestore
from pydantic import BaseModel

from firedantic.configurations import configure
from firedantic.models import Model


class Owner(BaseModel):
    """Dummy owner Pydantic model."""

    first_name: str
    last_name: str


class Company(Model):
    """Dummy company Firedantic model."""

    __collection__ = "companies"
    company_id: str
    owner: Owner


@pytest.fixture
def configure_db():
    client = firestore.Client(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    prefix = str(uuid.uuid4()) + "-"
    configure(client, prefix)


@pytest.fixture
def create_company():
    def _create(
        company_id: str = "1234567-8", first_name: str = "John", last_name: str = "Doe"
    ):
        owner = Owner(first_name=first_name, last_name=last_name)
        company = Company(company_id=company_id, owner=owner)
        company.save()
        return company

    return _create
