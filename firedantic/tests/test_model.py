from typing import List

import pytest
from firedantic.exceptions import ModelNotFoundError
from firedantic.tests.conftest import Company


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


def test_find(configure_db, create_company):
    ids = ["1234555-1", "1234567-8", "2131232-4", "4124432-4"]
    companies = []
    for company_id in ids:
        companies.append(create_company(company_id=company_id))

    c: List[Company] = Company.find({"company_id": "4124432-4"})
    assert c[0].company_id == "4124432-4"
    assert c[0].owner.first_name == "John"

    d: List[Company] = Company.find({"owner.first_name": "John"})
    assert len(d) == 4


def test_get_by_id(configure_db, create_company):
    c: Company = create_company(company_id="1234567-8")

    assert c.id is not None
    assert c.company_id == "1234567-8"
    assert c.owner.last_name == "Doe"

    c_2 = Company.get_by_id(c.id)

    assert c_2.id == c.id
    assert c_2.company_id == "1234567-8"
    assert c_2.owner.first_name == "John"
