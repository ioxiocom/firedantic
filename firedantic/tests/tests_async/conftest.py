import uuid
from datetime import datetime
from typing import List, Type
from unittest.mock import Mock

import google.auth.credentials
import pytest
from google.cloud.firestore_admin_v1 import Field, FirestoreAdminClient
from google.cloud.firestore_v1 import AsyncClient
from pydantic import BaseModel, Extra, PrivateAttr

from firedantic import (
    AsyncBareModel,
    AsyncBareSubCollection,
    AsyncBareSubModel,
    AsyncModel,
    AsyncSubCollection,
    AsyncSubModel,
)
from firedantic.configurations import configure
from firedantic.exceptions import ModelNotFoundError


class CustomIDModel(AsyncBareModel):
    __collection__ = "custom"
    __document_id__ = "foo"

    foo: str | None = None
    bar: str

    class Config:
        extra = Extra.forbid


class CustomIDModelExtra(AsyncBareModel):
    __collection__ = "custom"
    __document_id__ = "foo"

    foo: str | None = None
    bar: str
    baz: str

    class Config:
        extra = Extra.forbid


class CustomIDConflictModel(AsyncModel):
    __collection__ = "custom"

    foo: str
    bar: str

    class Config:
        extra = Extra.forbid


class Owner(BaseModel):
    """Dummy owner Pydantic model."""

    first_name: str
    last_name: str

    class Config:
        extra = Extra.forbid


class CompanyStats(AsyncBareSubModel):
    _doc_id: str | None = PrivateAttr()
    sales: int

    class Collection(AsyncBareSubCollection):
        __collection_tpl__ = "companies/{id}/Stats"
        __document_id__ = "_doc_id"

    @classmethod
    async def _get_by_id_or_empty(cls, _doc_id) -> AsyncBareSubModel:
        try:
            return await cls.get_by_doc_id(_doc_id)
        except ModelNotFoundError:
            model = cls._create(  # type: ignore
                sales=0,
            )
            model._doc_id = _doc_id
            return model  # type: ignore

    @classmethod
    async def get_stats(cls, period="2021"):
        return await cls._get_by_id_or_empty(period)


class Company(AsyncModel):
    """Dummy company Firedantic model."""

    __collection__ = "companies"
    company_id: str
    owner: Owner

    class Config:
        extra = Extra.forbid

    def stats(self) -> Type[CompanyStats]:
        return CompanyStats.model_for(self)  # type: ignore


class Product(AsyncModel):
    """Dummy product Firedantic model."""

    __collection__ = "products"
    product_id: str
    price: float
    stock: int

    class Config:
        extra = Extra.forbid


class TodoList(AsyncModel):
    __collection__ = "todoLists"
    name: str
    items: List[str]

    class Config:
        extra = Extra.forbid


class ExpiringModel(AsyncModel):
    __collection__ = "expiringModel"
    __ttl_field__ = "expire"

    expire: datetime
    content: str


@pytest.fixture
def configure_db():
    client = AsyncClient(
        project="ioxio-local-dev",
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


# Test case from README
class UserStats(AsyncSubModel):
    id: str | None = None
    purchases: int = 0

    class Collection(AsyncSubCollection):
        # Can use any properties of the "parent" model
        __collection_tpl__ = "users/{id}/stats"


class User(AsyncModel):
    __collection__ = "users"
    name: str


async def get_user_purchases(user_id: str, period: str = "2021") -> int:
    user = await User.get_by_id(user_id)
    stats_model: Type[UserStats] = UserStats.model_for(user)
    try:
        stats = await stats_model.get_by_id(period)
    except ModelNotFoundError:
        stats = stats_model()
    return stats.purchases


class MockOperation:
    pass


class AsyncMockFirestoreAdminClient:
    """
    Really minimal mock version of the Firestore Admin Client
    """

    # Copy implementation from the real class
    field_path = staticmethod(FirestoreAdminClient.field_path)

    def __init__(self):
        self.field_state: Field.TtlConfig.State = (
            Field.TtlConfig.State.STATE_UNSPECIFIED
        )
        self.updated_field = None

    def get_field_state(self) -> Field.TtlConfig.State:
        return self.field_state

    class MockField:
        class MockTTLConfig:
            def __init__(self, state_getter):
                self.state_getter = state_getter

            @property
            def state(self):
                return self.state_getter()

        def __init__(self, state_getter):
            self.ttl_config = self.MockTTLConfig(state_getter)

    async def get_field(self, *args, **kwargs) -> MockField:
        return self.MockField(self.get_field_state)

    async def update_field(self, data) -> MockOperation:
        self.updated_field = data
        return MockOperation()


@pytest.fixture()
def mock_admin_client():
    return AsyncMockFirestoreAdminClient()
