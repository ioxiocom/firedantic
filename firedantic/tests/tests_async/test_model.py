import pytest
from pydantic import Field, ValidationError

import firedantic.operators as op
from firedantic import AsyncModel
from firedantic.exceptions import CollectionNotDefined, ModelNotFoundError
from firedantic.tests.tests_async.conftest import (
    Company,
    CustomIDConflictModel,
    CustomIDModel,
    CustomIDModelExtra,
    Product,
    TodoList,
    User,
    UserStats,
    get_user_purchases,
)

TEST_PRODUCTS = [
    {"product_id": "a", "stock": 0},
    {"product_id": "b", "stock": 1},
    {"product_id": "c", "stock": 2},
    {"product_id": "d", "stock": 3},
]


@pytest.mark.asyncio
async def test_save_model(configure_db, create_company):
    company = await create_company()

    assert company.id is not None
    assert company.owner.first_name == "John"
    assert company.owner.last_name == "Doe"


@pytest.mark.asyncio
async def test_delete_model(configure_db, create_company):
    company: Company = await create_company(
        company_id="11223344-5", first_name="Jane", last_name="Doe"
    )

    _id = company.id

    await company.delete()

    with pytest.raises(ModelNotFoundError):
        await Company.get_by_id(_id)


@pytest.mark.asyncio
async def test_find_one(configure_db, create_company):
    with pytest.raises(ModelNotFoundError):
        await Company.find_one()

    company_a: Company = await create_company(company_id="1234555-1", first_name="Foo")
    company_b: Company = await create_company(company_id="1231231-2", first_name="Bar")

    a: Company = await Company.find_one({"company_id": company_a.company_id})
    b: Company = await Company.find_one({"company_id": company_b.company_id})

    assert a.company_id == company_a.company_id
    assert b.company_id == company_b.company_id
    assert a.owner.first_name == "Foo"
    assert b.owner.first_name == "Bar"

    with pytest.raises(ModelNotFoundError):
        await Company.find_one({"company_id": "Foo"})

    random_company = await Company.find_one()
    assert random_company.company_id in {a.company_id, b.company_id}


@pytest.mark.asyncio
async def test_find(configure_db, create_company, create_product):
    ids = ["1234555-1", "1234567-8", "2131232-4", "4124432-4"]
    for company_id in ids:
        await create_company(company_id=company_id)

    c = await Company.find({"company_id": "4124432-4"})
    assert c[0].company_id == "4124432-4"
    assert c[0].owner.first_name == "John"

    d = await Company.find({"owner.first_name": "John"})
    assert len(d) == 4

    for p in TEST_PRODUCTS:
        await create_product(**p)

    assert len(await Product.find({})) == 4

    products = await Product.find({"stock": {op.GTE: 1}})
    assert len(products) == 3

    products = await Product.find({"stock": {op.GTE: 2, op.LT: 4}})
    assert len(products) == 2

    products = await Product.find({"product_id": {op.IN: ["a", "d", "g"]}})
    assert len(products) == 2

    with pytest.raises(ValueError):
        await Product.find({"product_id": {"<>": "a"}})


@pytest.mark.asyncio
async def test_find_not_in(configure_db, create_company):
    ids = ["1234555-1", "1234567-8", "2131232-4", "4124432-4"]
    for company_id in ids:
        await create_company(company_id=company_id)

    found = await Company.find(
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


@pytest.mark.asyncio
async def test_find_array_contains(configure_db, create_todolist):
    list_1 = await create_todolist("list_1", ["Work", "Eat", "Sleep"])
    await create_todolist("list_2", ["Learn Python", "Walk the dog"])

    found = await TodoList.find({"items": {op.ARRAY_CONTAINS: "Eat"}})
    assert len(found) == 1
    assert found[0].name == list_1.name


@pytest.mark.asyncio
async def test_find_array_contains_any(configure_db, create_todolist):
    list_1 = await create_todolist("list_1", ["Work", "Eat"])
    list_2 = await create_todolist("list_2", ["Relax", "Chill", "Sleep"])
    await create_todolist("list_3", ["Learn Python", "Walk the dog"])

    found = await TodoList.find({"items": {op.ARRAY_CONTAINS_ANY: ["Eat", "Sleep"]}})
    assert len(found) == 2
    for lst in found:
        assert lst.name in (list_1.name, list_2.name)


@pytest.mark.asyncio
async def test_get_by_id(configure_db, create_company):
    c: Company = await create_company(company_id="1234567-8")

    assert c.id is not None
    assert c.company_id == "1234567-8"
    assert c.owner.last_name == "Doe"

    c_2 = await Company.get_by_id(c.id)

    assert c_2.id == c.id
    assert c_2.company_id == "1234567-8"
    assert c_2.owner.first_name == "John"


@pytest.mark.asyncio
async def test_get_by_empty_str_id(configure_db):
    with pytest.raises(ModelNotFoundError):
        await Company.get_by_id("")


@pytest.mark.asyncio
async def test_missing_collection(configure_db):
    class User(AsyncModel):
        name: str

    with pytest.raises(CollectionNotDefined):
        await User(name="John").save()


@pytest.mark.asyncio
async def test_model_aliases(configure_db):
    class User(AsyncModel):
        __collection__ = "User"

        first_name: str = Field(..., alias="firstName")
        city: str

    user = User(firstName="John", city="Helsinki")
    await user.save()

    user_from_db = await User.get_by_id(user.id)
    assert user_from_db.first_name == "John"
    assert user_from_db.city == "Helsinki"


@pytest.mark.asyncio
async def test_truncate_collection(configure_db, create_company):
    await create_company(company_id="1234567-8")
    await create_company(company_id="1234567-9")

    companies = await Company.find({})
    assert len(companies) == 2

    await Company.truncate_collection()
    new_companies = await Company.find({})
    assert len(new_companies) == 0


@pytest.mark.asyncio
async def test_custom_id_model(configure_db):
    c = CustomIDModel(bar="bar")
    await c.save()

    models = await CustomIDModel.find({})
    assert len(models) == 1

    m = models[0]
    assert m.foo is not None
    assert m.bar == "bar"


@pytest.mark.asyncio
async def test_custom_id_conflict(configure_db):
    await CustomIDConflictModel(foo="foo", bar="bar").save()

    models = await CustomIDModel.find({})
    assert len(models) == 1

    m = models[0]
    assert m.foo != "foo"
    assert m.bar == "bar"


@pytest.mark.asyncio
async def test_model_id_persistency(configure_db):
    c = CustomIDConflictModel(foo="foo", bar="bar")
    await c.save()

    c = await CustomIDConflictModel.get_by_doc_id(c.id)
    await c.save()

    assert len(await CustomIDConflictModel.find({})) == 1


@pytest.mark.asyncio
async def test_bare_model_document_id_persistency(configure_db):
    c = CustomIDModel(bar="bar")
    await c.save()

    c = await CustomIDModel.get_by_doc_id(c.foo)
    await c.save()

    assert len(await CustomIDModel.find({})) == 1


@pytest.mark.asyncio
async def test_bare_model_get_by_empty_doc_id(configure_db):
    with pytest.raises(ModelNotFoundError):
        await CustomIDModel.get_by_doc_id("")


@pytest.mark.asyncio
async def test_extra_fields(configure_db):
    await CustomIDModelExtra(foo="foo", bar="bar", baz="baz").save()
    with pytest.raises(ValidationError):
        await CustomIDModel.find({})


@pytest.mark.asyncio
async def test_company_stats(configure_db, create_company):
    company: Company = await create_company(company_id="1234567-8")
    company_stats = company.stats()

    stats = await company_stats.get_stats()
    stats.sales = 100
    await stats.save()

    # Ensure the data can be still loaded
    loaded = await company.stats().get_stats()
    assert loaded.sales == stats.sales

    # And that we can still save
    loaded.sales += 1
    await loaded.save()

    stats = await company_stats.get_stats()
    assert stats.sales == 101


@pytest.mark.asyncio
async def test_subcollection_model_safety(configure_db):
    """
    Ensure you shouldn't be able to use unprepared subcollection models accidentally
    """
    with pytest.raises(CollectionNotDefined):
        await UserStats.find({})


@pytest.mark.asyncio
async def test_get_user_purchases(configure_db):
    u = User(name="Foo")
    await u.save()

    us = UserStats.model_for(u)
    await us(id="2021", purchases=42).save()

    assert await get_user_purchases(u.id) == 42
