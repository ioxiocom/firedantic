import uuid
from typing import List
from unittest.mock import Mock

import google.auth.credentials
import pytest
from google.cloud.firestore_v1 import AsyncClient
from pydantic import BaseModel

from firedantic import AsyncModel
from firedantic.configurations import configure


class Owner(BaseModel):
    """Dummy owner Pydantic model."""

    first_name: str
    last_name: str


class Company(AsyncModel):
    """Dummy company Firedantic model."""

    __collection__ = "companies"
    company_id: str
    owner: Owner


class Product(AsyncModel):
    """Dummy product Firedantic model."""

    __collection__ = "products"
    product_id: str
    price: float
    stock: int


class TodoList(AsyncModel):
    __collection__ = "todoLists"
    name: str
    items: List[str]


@pytest.fixture
def configure_db():
    client = AsyncClient(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    prefix = str(uuid.uuid4()) + "-"
    configure(client, prefix)


@pytest.fixture
def create_company():
    async def _create(
        company_id: str = "1234567-8", first_name: str = "John", last_name: str = "Doe"
    ):
        owner = Owner(first_name=first_name, last_name=last_name)
        company = Company(company_id=company_id, owner=owner)
        await company.save()
        return company

    return _create


@pytest.fixture
def create_product():
    async def _create(product_id: str = None, price: float = 1.23, stock: int = 3):
        if not product_id:
            product_id = str(uuid.uuid4())
        p = Product(product_id=product_id, price=price, stock=stock)
        await p.save()
        return p

    return _create


@pytest.fixture
def create_todolist():
    async def _create(name: str, items: List[str]):
        p = TodoList(name=name, items=items)
        await p.save()
        return p

    return _create
