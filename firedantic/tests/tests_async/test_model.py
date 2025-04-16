from operator import attrgetter
from uuid import uuid4

import pytest
from google.cloud.firestore import Query, async_transactional
from google.cloud.firestore_v1.async_transaction import AsyncTransaction
from pydantic import Field, ValidationError

import firedantic.operators as op
from firedantic import AsyncModel
from firedantic.configurations import CONFIGURATIONS
from firedantic.exceptions import (
    CollectionNotDefined,
    InvalidDocumentID,
    ModelNotFoundError,
)
from firedantic.tests.tests_async.conftest import (
    Company,
    CustomIDConflictModel,
    CustomIDModel,
    CustomIDModelExtra,
    Product,
    Profile,
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
async def test_save_model(configure_db, create_company) -> None:
    company = await create_company()

    assert company.id is not None
    assert company.owner.first_name == "John"
    assert company.owner.last_name == "Doe"


@pytest.mark.asyncio
async def test_delete_model(configure_db, create_company) -> None:
    company: Company = await create_company(
        company_id="11223344-5", first_name="Jane", last_name="Doe"
    )

    _id = company.id
    assert _id

    await company.delete()

    with pytest.raises(ModelNotFoundError):
        await Company.get_by_id(_id)


@pytest.mark.asyncio
async def test_find_one(configure_db, create_company) -> None:
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

    first_asc = await Company.find_one(order_by=[("owner.first_name", Query.ASCENDING)])
    assert first_asc.owner.first_name == "Bar"

    first_desc = await Company.find_one(
        order_by=[("owner.first_name", Query.DESCENDING)]
    )
    assert first_desc.owner.first_name == "Foo"


@pytest.mark.asyncio
async def test_find(configure_db, create_company, create_product) -> None:
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
async def test_find_not_in(configure_db, create_company) -> None:
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
async def test_find_array_contains(configure_db, create_todolist) -> None:
    list_1 = await create_todolist("list_1", ["Work", "Eat", "Sleep"])
    await create_todolist("list_2", ["Learn Python", "Walk the dog"])

    found = await TodoList.find({"items": {op.ARRAY_CONTAINS: "Eat"}})
    assert len(found) == 1
    assert found[0].name == list_1.name


@pytest.mark.asyncio
async def test_find_array_contains_any(configure_db, create_todolist) -> None:
    list_1 = await create_todolist("list_1", ["Work", "Eat"])
    list_2 = await create_todolist("list_2", ["Relax", "Chill", "Sleep"])
    await create_todolist("list_3", ["Learn Python", "Walk the dog"])

    found = await TodoList.find({"items": {op.ARRAY_CONTAINS_ANY: ["Eat", "Sleep"]}})
    assert len(found) == 2
    for lst in found:
        assert lst.name in (list_1.name, list_2.name)


@pytest.mark.asyncio
async def test_find_limit(configure_db, create_company) -> None:
    ids = ["1234555-1", "1234567-8", "2131232-4", "4124432-4"]
    for company_id in ids:
        await create_company(company_id=company_id)

    companies_all = await Company.find()
    assert len(companies_all) == 4

    companies_2 = await Company.find(limit=2)
    assert len(companies_2) == 2


@pytest.mark.asyncio
async def test_find_order_by(configure_db, create_company) -> None:
    companies_and_owners = [
        {"company_id": "1234555-1", "last_name": "A", "first_name": "A"},
        {"company_id": "1234555-2", "last_name": "A", "first_name": "B"},
        {"company_id": "1234567-8", "last_name": "B", "first_name": "C"},
        {"company_id": "1234567-9", "last_name": "B", "first_name": "D"},
        {"company_id": "2131232-4", "last_name": "C", "first_name": "E"},
        {"company_id": "2131232-5", "last_name": "C", "first_name": "F"},
        {"company_id": "4124432-4", "last_name": "D", "first_name": "G"},
        {"company_id": "4124432-5", "last_name": "D", "first_name": "H"},
    ]

    companies_and_owners = [
        await create_company(**item) for item in companies_and_owners
    ]

    companies_ascending = await Company.find(
        order_by=[("owner.first_name", Query.ASCENDING)]
    )
    assert companies_ascending == companies_and_owners

    companies_descending = await Company.find(
        order_by=[("owner.first_name", Query.DESCENDING)]
    )
    reversed_companies_and_owners = list(reversed(companies_and_owners))
    assert companies_descending == reversed_companies_and_owners

    lastname_ascending_firstname_descending = await Company.find(
        order_by=[
            ("owner.last_name", Query.ASCENDING),
            ("owner.first_name", Query.DESCENDING),
        ]
    )
    expected = sorted(
        companies_and_owners, key=attrgetter("owner.first_name"), reverse=True
    )
    expected = sorted(expected, key=attrgetter("owner.last_name"))
    assert expected == lastname_ascending_firstname_descending

    lastname_ascending_firstname_ascending = await Company.find(
        order_by=[
            ("owner.last_name", Query.ASCENDING),
            ("owner.first_name", Query.ASCENDING),
        ]
    )
    assert companies_and_owners == lastname_ascending_firstname_ascending


@pytest.mark.asyncio
async def test_find_offset(configure_db, create_company) -> None:
    ids_and_lastnames = (
        ("1234555-1", "A"),
        ("1234567-8", "B"),
        ("2131232-4", "C"),
        ("4124432-4", "D"),
    )
    for company_id, lastname in ids_and_lastnames:
        await create_company(company_id=company_id, last_name=lastname)
    companies_ascending = await Company.find(
        order_by=[("owner.last_name", Query.ASCENDING)], offset=2
    )
    assert companies_ascending[0].owner.last_name == "C"
    assert companies_ascending[1].owner.last_name == "D"
    assert len(companies_ascending) == 2


@pytest.mark.asyncio
async def test_get_by_id(configure_db, create_company) -> None:
    c: Company = await create_company(company_id="1234567-8")

    assert c.id is not None
    assert c.company_id == "1234567-8"
    assert c.owner.last_name == "Doe"

    c_2 = await Company.get_by_id(c.id)

    assert c_2.id == c.id
    assert c_2.company_id == "1234567-8"
    assert c_2.owner.first_name == "John"


@pytest.mark.asyncio
async def test_get_by_empty_str_id(configure_db) -> None:
    with pytest.raises(ModelNotFoundError):
        await Company.get_by_id("")


@pytest.mark.asyncio
async def test_missing_collection(configure_db) -> None:
    class User(AsyncModel):
        name: str

    with pytest.raises(CollectionNotDefined):
        await User(name="John").save()


@pytest.mark.asyncio
async def test_model_aliases(configure_db) -> None:
    class User(AsyncModel):
        __collection__ = "User"

        first_name: str = Field(..., alias="firstName")
        city: str

    user = User(firstName="John", city="Helsinki")
    await user.save()
    assert user.id

    user_from_db = await User.get_by_id(user.id)
    assert user_from_db.first_name == "John"
    assert user_from_db.city == "Helsinki"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_id",
    [
        "abc",
        pytest.param("a" * 1500, id="1500 chars"),
        "...",
        ".foo",
        "..bar",
        "f..oo",
        "bar..",
        "__",
        "___",
        "_foo_",
        "__bar_",
        "_baz__",
        "b__a__r",
        "å",
        "😀",
        " ",
        '"',
        "'",
        "\\",
        "\x00",
        "\x01",
        "\x07",
        "!:&+-*'()",
    ],
)
async def test_models_with_valid_custom_id(configure_db, model_id) -> None:
    product_id = str(uuid4())

    product = Product(product_id=product_id, price=123.45, stock=2)
    product.id = model_id
    await product.save()

    found = await Product.get_by_id(model_id)
    assert found.product_id == product_id

    await found.delete()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "model_id",
    [
        "",
        pytest.param("a" * 1501, id="1501 chars"),
        ".",
        "..",
        "____",
        "__foo__",
        "__😀__",
        "/",
        "foo/bar",
        "foo/bar/baz",
    ],
)
async def test_models_with_invalid_custom_id(configure_db, model_id: str) -> None:
    product = Product(product_id="product 123", price=123.45, stock=2)
    product.id = model_id
    with pytest.raises(InvalidDocumentID):
        await product.save()

    with pytest.raises(ModelNotFoundError):
        await Product.get_by_id(model_id)


@pytest.mark.asyncio
async def test_truncate_collection(configure_db, create_company) -> None:
    await create_company(company_id="1234567-8")
    await create_company(company_id="1234567-9")

    companies = await Company.find({})
    assert len(companies) == 2

    await Company.truncate_collection()
    new_companies = await Company.find({})
    assert len(new_companies) == 0


@pytest.mark.asyncio
async def test_custom_id_model(configure_db) -> None:
    c = CustomIDModel(bar="bar")  # type: ignore
    await c.save()

    models = await CustomIDModel.find({})
    assert len(models) == 1

    m = models[0]
    assert m.foo is not None
    assert m.bar == "bar"


@pytest.mark.asyncio
async def test_custom_id_conflict(configure_db) -> None:
    await CustomIDConflictModel(foo="foo", bar="bar").save()

    models = await CustomIDModel.find({})
    assert len(models) == 1

    m = models[0]
    assert m.foo != "foo"
    assert m.bar == "bar"


@pytest.mark.asyncio
async def test_model_id_persistency(configure_db) -> None:
    c = CustomIDConflictModel(foo="foo", bar="bar")
    await c.save()
    assert c.id

    c = await CustomIDConflictModel.get_by_doc_id(c.id)
    await c.save()

    assert len(await CustomIDConflictModel.find({})) == 1


@pytest.mark.asyncio
async def test_bare_model_document_id_persistency(configure_db) -> None:
    c = CustomIDModel(bar="bar")  # type: ignore
    await c.save()
    assert c.foo

    c = await CustomIDModel.get_by_doc_id(c.foo)
    await c.save()

    assert len(await CustomIDModel.find({})) == 1


@pytest.mark.asyncio
async def test_bare_model_get_by_empty_doc_id(configure_db) -> None:
    with pytest.raises(ModelNotFoundError):
        await CustomIDModel.get_by_doc_id("")


@pytest.mark.asyncio
async def test_extra_fields(configure_db) -> None:
    await CustomIDModelExtra(foo="foo", bar="bar", baz="baz").save()  # type: ignore
    with pytest.raises(ValidationError):
        await CustomIDModel.find({})


@pytest.mark.asyncio
async def test_company_stats(configure_db, create_company) -> None:
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
async def test_subcollection_model_safety(configure_db) -> None:
    """
    Ensure you shouldn't be able to use unprepared subcollection models accidentally
    """
    with pytest.raises(CollectionNotDefined):
        await UserStats.find({})


@pytest.mark.asyncio
async def test_get_user_purchases(configure_db) -> None:
    u = User(name="Foo")
    await u.save()
    assert u.id

    us = UserStats.model_for(u)
    await us(id="2021", purchases=42).save()

    assert await get_user_purchases(u.id) == 42


@pytest.mark.asyncio
async def test_reload(configure_db) -> None:
    u = User(name="Foo")
    await u.save()

    # change the value in the database
    u_ = await User.find_one({"name": "Foo"})
    u_.name = "Bar"
    await u_.save()

    assert u.name == "Foo"
    await u.reload()
    assert u.name == "Bar"

    another_user = User(name="Another")
    with pytest.raises(ModelNotFoundError):
        await another_user.reload()


@pytest.mark.asyncio
async def test_save_with_exclude_none(configure_db) -> None:
    p = Profile(name="Foo")
    await p.save(exclude_none=True)

    document_id = p.get_document_id()
    assert document_id

    # pylint: disable=protected-access
    document = await Profile._get_col_ref().document(document_id).get()

    data = document.to_dict()
    assert data == {"name": "Foo"}
    await p.save()

    # pylint: disable=protected-access
    document = await Profile._get_col_ref().document(document_id).get()

    data = document.to_dict()
    assert data == {"name": "Foo", "email": None, "photo_url": None}


@pytest.mark.asyncio
async def test_save_with_exclude_unset(configure_db) -> None:
    p = Profile(photo_url=None)
    await p.save(exclude_unset=True)

    document_id = p.get_document_id()
    assert document_id

    # pylint: disable=protected-access
    document = await Profile._get_col_ref().document(document_id).get()

    data = document.to_dict()
    assert data == {"photo_url": None}
    await p.save()

    # pylint: disable=protected-access
    document = await Profile._get_col_ref().document(document_id).get()

    data = document.to_dict()
    assert data == {"name": "", "email": None, "photo_url": None}


@pytest.mark.asyncio
async def test_create_in_transaction(configure_db) -> None:
    """Test creating a model in a transaction. Test case from README."""

    @async_transactional  # type: ignore
    async def create_in_transaction(transaction, email) -> Profile:
        """Creates a Profile in a transaction"""
        try:
            await Profile.find_one({"email": email}, transaction=transaction)
            raise ValueError(f"Profile already exists with email: {email}")
        except ModelNotFoundError:
            p = Profile(email=email)
            await p.save(transaction=transaction)
            return p

    transaction = CONFIGURATIONS["db"].transaction()
    p = await create_in_transaction(transaction, "test@example.com")
    assert isinstance(p, Profile)
    assert p.id

    transaction2 = CONFIGURATIONS["db"].transaction()
    with pytest.raises(ValueError) as excinfo:
        await create_in_transaction(transaction2, "test@example.com")
    assert str(excinfo.value) == "Profile already exists with email: test@example.com"


@pytest.mark.asyncio
async def test_delete_in_transaction(configure_db) -> None:
    """Test deleting a model in a transaction."""

    @async_transactional  # type: ignore
    async def delete_in_transaction(
        transaction: AsyncTransaction, profile_id: str
    ) -> dict:
        """Deletes a Profile in a transaction."""
        try:
            p = await Profile.get_by_id(profile_id, transaction=transaction)
            await p.delete(transaction=transaction)
            return {"id": profile_id}
        except ModelNotFoundError:
            raise ValueError(f"Profile not found: {profile_id}")

    p = Profile(name="Foo")
    await p.save()
    assert p.id

    transaction = CONFIGURATIONS["db"].transaction()
    result = await delete_in_transaction(transaction, p.id)
    assert isinstance(result, dict)
    assert result == {"id": p.id}

    transaction2 = CONFIGURATIONS["db"].transaction()
    with pytest.raises(ValueError) as excinfo:
        await delete_in_transaction(transaction2, p.id)
    assert str(excinfo.value) == f"Profile not found: {p.id}"


@pytest.mark.asyncio
async def test_update_model_in_transaction(configure_db) -> None:
    """Test updating a model in a transaction."""

    @async_transactional  # type: ignore
    async def update_in_transaction(
        transaction: AsyncTransaction, profile_id: str, name: str
    ) -> Profile:
        """Updates a Profile in a transaction."""
        p = Profile(id=profile_id)
        await p.reload(transaction=transaction)
        p.name = name
        await p.save(transaction=transaction)
        return p

    p = Profile(name="Foo")
    await p.save()
    assert p.id

    transaction = CONFIGURATIONS["db"].transaction()
    result = await update_in_transaction(transaction, p.id, "Bar")
    assert isinstance(result, Profile)
    assert result.id == p.id
    assert result.name == "Bar"


@pytest.mark.asyncio
async def test_update_submodel_in_transaction(configure_db) -> None:
    """Test Updating a submodel in a transaction."""

    @async_transactional  # type: ignore
    async def update_submodel_in_transaction(
        transaction: AsyncTransaction, user_id: str, period: str, purchases: int
    ) -> UserStats:
        """Updates a UserStats in a transaction."""
        u = await User.get_by_id(user_id)
        us = UserStats.model_for(u)
        user_stats: UserStats = await us.get_by_id(period)  # pylint: disable=no-member
        user_stats.purchases = purchases
        await user_stats.save(transaction=transaction)
        return user_stats

    u = User(name="Foo")
    await u.save()
    assert u.id
    us = UserStats.model_for(u)
    await us(id="2021", purchases=42).save()  # pylint: disable=no-member

    transaction = CONFIGURATIONS["db"].transaction()
    user_stats = await update_submodel_in_transaction(transaction, u.id, "2021", 43)
    assert isinstance(user_stats, UserStats)
    assert user_stats.purchases == 43
    assert await get_user_purchases(u.id) == 43
