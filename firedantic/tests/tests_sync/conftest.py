import uuid
from typing import List, Optional, Type
from unittest.mock import Mock

import google.auth.credentials
import pytest
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


class CustomIDModel(BareModel):
    __collection__ = "custom"
    __document_id__ = "foo"

    foo: Optional[str]
    bar: str

    class Config:
        extra = Extra.forbid


class CustomIDModelExtra(BareModel):
    __collection__ = "custom"
    __document_id__ = "foo"

    foo: Optional[str]
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


class TodoList(Model):
    __collection__ = "todoLists"
    name: str
    items: List[str]

    class Config:
        extra = Extra.forbid


@pytest.fixture
def configure_db():
    client = Client(
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


@pytest.fixture
def create_product():
    def _create(product_id: str = None, price: float = 1.23, stock: int = 3):
        if not product_id:
            product_id = str(uuid.uuid4())
        p = Product(product_id=product_id, price=price, stock=stock)
        p.save()
        return p

    return _create


@pytest.fixture
def create_todolist():
    def _create(name: str, items: List[str]):
        p = TodoList(name=name, items=items)
        p.save()
        return p

    return _create


# Test case from README
class UserStats(SubModel):
    id: Optional[str]
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
