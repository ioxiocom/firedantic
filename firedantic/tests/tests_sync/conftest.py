import uuid
from datetime import datetime
from typing import Any, List, Optional, Type

import google.auth.credentials
import pytest
from google.cloud.firestore_admin_v1 import Field, FirestoreAdminClient
from google.cloud.firestore_v1 import Client
from pydantic import BaseModel, Extra, PrivateAttr

from firedantic import (
    BareModel,
    BareSubCollection,
    BareSubModel,
    Model,
    SubCollection,
    SubModel,
)
from firedantic.configurations import configure
from firedantic.exceptions import ModelNotFoundError

from unittest.mock import Mock, Mock  # noqa isort: skip


class CustomIDModel(BareModel):
    __collection__ = "custom"
    __document_id__ = "foo"

    foo: Optional[str] = None
    bar: str

    class Config:
        extra = Extra.forbid


class CustomIDModelExtra(BareModel):
    __collection__ = "custom"
    __document_id__ = "foo"

    foo: Optional[str] = None
    bar: str
    baz: str

    class Config:
        extra = Extra.forbid


class CustomIDConflictModel(Model):
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


class CompanyStats(BareSubModel):
    _doc_id: Optional[str] = PrivateAttr()

    sales: int

    class Collection(BareSubCollection):
        __collection_tpl__ = "companies/{id}/Stats"
        __document_id__ = "_doc_id"

    @classmethod
    def _get_by_id_or_empty(cls, _doc_id) -> BareSubModel:
        try:
            return cls.get_by_doc_id(_doc_id)
        except ModelNotFoundError:
            model = cls._create(  # type: ignore
                sales=0,
            )
            model._doc_id = _doc_id
            return model  # type: ignore

    @classmethod
    def get_stats(cls, period="2021"):
        return cls._get_by_id_or_empty(period)


class Company(Model):
    """Dummy company Firedantic model."""

    __collection__ = "companies"

    company_id: str
    owner: Owner

    class Config:
        extra = Extra.forbid

    def stats(self) -> Type[CompanyStats]:
        return CompanyStats.model_for(self)  # type: ignore


class Product(Model):
    """Dummy product Firedantic model."""

    __collection__ = "products"

    product_id: str
    price: float
    stock: int

    class Config:
        extra = Extra.forbid


class Profile(Model):
    """Dummy profile Firedantic model."""

    __collection__ = "profiles"

    name: Optional[str] = ""
    photo_url: Optional[str] = None

    class Config:
        extra = Extra.forbid


class TodoList(Model):
    """Dummy todo list Firedantic model."""

    __collection__ = "todoLists"

    name: str
    items: List[str]

    class Config:
        extra = Extra.forbid


class ExpiringModel(Model):
    """Dummy expiring model Firedantic model."""

    __collection__ = "expiringModel"
    __ttl_field__ = "expire"

    expire: datetime
    content: str


@pytest.fixture(autouse=True)
def configure_db():
    client = Client(
        project="ioxio-local-dev",
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


@pytest.fixture
def create_product():
    def _create(product_id: Optional[str] = None, price: float = 1.23, stock: int = 3):
        if not product_id:
            product_id = str(uuid.uuid4())
        p = Product(product_id=product_id, price=price, stock=stock)
        p.save()
        return p

    return _create


@pytest.fixture
def create_todolist():
    def _create(name: str, items: List[str]):
        t = TodoList(name=name, items=items)
        t.save()
        return t

    return _create


# Test case from README
class UserStats(SubModel):
    id: Optional[str] = None
    purchases: int = 0

    class Collection(SubCollection):
        # Can use any properties of the "parent" model
        __collection_tpl__ = "users/{id}/stats"


class User(Model):
    __collection__ = "users"
    name: str


def get_user_purchases(user_id: str, period: str = "2021") -> int:
    user = User.get_by_id(user_id)
    stats_model: Type[UserStats] = UserStats.model_for(user)
    try:
        stats = stats_model.get_by_id(period)
    except ModelNotFoundError:
        stats = stats_model()
    return stats.purchases


class MockOperation:
    pass


class MockListIndexPages:
    def __init__(self, pages: List[Any]):
        self._pages = pages
        self._i = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self._i == len(self._pages):
            raise StopIteration
        self._i += 1
        return self._pages[self._i - 1]


class MockListIndexOperation:
    def __init__(self, pages: List[Any]):
        self.pages = MockListIndexPages(pages)


class MockFirestoreAdminClient:
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
        self.list_indexes = Mock(return_value=MockListIndexOperation([]))
        self.create_index = Mock()

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

    def get_field(self, *args, **kwargs) -> MockField:
        return self.MockField(self.get_field_state)

    def update_field(self, data) -> MockOperation:
        self.updated_field = data
        return MockOperation()


@pytest.fixture()
def mock_admin_client():
    return MockFirestoreAdminClient()
