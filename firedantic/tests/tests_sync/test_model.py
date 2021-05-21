import pytest
from pydantic import Field

import firedantic.operators as op
from firedantic import Model
from firedantic.exceptions import CollectionNotDefined, ModelNotFoundError
from firedantic.tests.tests_sync.conftest import Company, Product, TodoList

TEST_PRODUCTS = [
    {"product_id": "a", "stock": 0},
    {"product_id": "b", "stock": 1},
    {"product_id": "c", "stock": 2},
    {"product_id": "d", "stock": 3},
]


def test_save_model(configure_db, create_company):
    company = create_company()

    assert company.id is not None
    assert company.owner.first_name == "John"
    assert company.owner.last_name == "Doe"


def test_delete_model(configure_db, create_company):
    company: Company = create_company(
        company_id="11223344-5", first_name="Jane", last_name="Doe"
    )

    _id = company.id

    company.delete()

    with pytest.raises(ModelNotFoundError):
        Company.get_by_id(_id)


def test_find_one(configure_db, create_company):
    with pytest.raises(ModelNotFoundError):
        Company.find_one()

    company_a: Company = create_company(company_id="1234555-1", first_name="Foo")
    company_b: Company = create_company(company_id="1231231-2", first_name="Bar")

    a: Company = Company.find_one({"company_id": company_a.company_id})
    b: Company = Company.find_one({"company_id": company_b.company_id})

    assert a.company_id == company_a.company_id
    assert b.company_id == company_b.company_id
    assert a.owner.first_name == "Foo"
    assert b.owner.first_name == "Bar"

    with pytest.raises(ModelNotFoundError):
        Company.find_one({"company_id": "Foo"})

    random_company = Company.find_one()
    assert random_company.company_id in {a.company_id, b.company_id}


def test_find(configure_db, create_company, create_product):
    ids = ["1234555-1", "1234567-8", "2131232-4", "4124432-4"]
    for company_id in ids:
        create_company(company_id=company_id)

    c = Company.find({"company_id": "4124432-4"})
    assert c[0].company_id == "4124432-4"
    assert c[0].owner.first_name == "John"

    d = Company.find({"owner.first_name": "John"})
    assert len(d) == 4

    for p in TEST_PRODUCTS:
        create_product(**p)

    assert len(Product.find({})) == 4

    products = Product.find({"stock": {op.GTE: 1}})
    assert len(products) == 3

    products = Product.find({"stock": {op.GTE: 2, op.LT: 4}})
    assert len(products) == 2

    products = Product.find({"product_id": {op.IN: ["a", "d", "g"]}})
    assert len(products) == 2

    with pytest.raises(ValueError):
        Product.find({"product_id": {"<>": "a"}})


def test_find_not_in(configure_db, create_company):
    ids = ["1234555-1", "1234567-8", "2131232-4", "4124432-4"]
    for company_id in ids:
        create_company(company_id=company_id)

    found = Company.find(
        {
            "company_id": {
                op.NOT_IN: [
                    "1234555-1",
                    "1234567-8",
                ]
            }
        }
    )
    assert len(found) == 2
    for company in found:
        assert company.company_id in ("2131232-4", "4124432-4")


def test_find_array_contains(configure_db, create_todolist):
    list_1 = create_todolist("list_1", ["Work", "Eat", "Sleep"])
    create_todolist("list_2", ["Learn Python", "Walk the dog"])

    found = TodoList.find({"items": {op.ARRAY_CONTAINS: "Eat"}})
    assert len(found) == 1
    assert found[0].name == list_1.name


def test_find_array_contains_any(configure_db, create_todolist):
    list_1 = create_todolist("list_1", ["Work", "Eat"])
    list_2 = create_todolist("list_2", ["Relax", "Chill", "Sleep"])
    create_todolist("list_3", ["Learn Python", "Walk the dog"])

    found = TodoList.find({"items": {op.ARRAY_CONTAINS_ANY: ["Eat", "Sleep"]}})
    assert len(found) == 2
    for lst in found:
        assert lst.name in (list_1.name, list_2.name)


def test_get_by_id(configure_db, create_company):
    c: Company = create_company(company_id="1234567-8")

    assert c.id is not None
    assert c.company_id == "1234567-8"
    assert c.owner.last_name == "Doe"

    c_2 = Company.get_by_id(c.id)

    assert c_2.id == c.id
    assert c_2.company_id == "1234567-8"
    assert c_2.owner.first_name == "John"


def test_missing_collection(configure_db):
    class User(Model):
        name: str

    with pytest.raises(CollectionNotDefined):
        User(name="John").save()


def test_model_aliases(configure_db):
    class User(Model):
        __collection__ = "User"

        first_name: str = Field(..., alias="firstName")
        city: str

    user = User(firstName="John", city="Helsinki")
    user.save()

    user_from_db = User.get_by_id(user.id)
    assert user_from_db.first_name == "John"
    assert user_from_db.city == "Helsinki"


def test_truncate_collection(configure_db, create_company):
    create_company(company_id="1234567-8")
    create_company(company_id="1234567-9")

    companies = Company.find({})
    assert len(companies) == 2

    Company.truncate_collection()
    new_companies = Company.find({})
    assert len(new_companies) == 0
