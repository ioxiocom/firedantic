from unittest.mock import Mock

from pydantic import BaseAsyncModel
from firedantic import AsyncModel
from firedantic.configurations import configuration, AsyncClient

import google.auth.credentials
import sys


## With single async client
async def old_way():
    
    class Owner(AsyncModel):
        """Dummy owner Pydantic model."""
        __collection__ = "owners"
        first_name: str
        last_name: str


    class Company(AsyncModel):
        """Dummy company Firedantic model."""
        __collection__ = "companies"
        company_id: str
        owner: Owner
    
    # Firestore emulator must be running if using locally, name defaults to "(default)"
    configuration.add(
        prefix="async-default-test-",
        project="async-default-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Now you can use the model to save it to Firestore
    owner = Owner(first_name="John", last_name="Doe")
    company = Company(company_id="1234567-8a", owner=owner)

    # Save the company/owner info to the DB  
    await company.save()  # only need to include config_name when not using default

    # Reloads model data from the database to ensure most-up-to-date info
    await company.reload()

    # Assert that async client exists and configuration is correct
    assert isinstance(configuration.get_async_client(), AsyncClient)
    assert configuration.get_collection_name(Owner) == configuration.get_config().prefix + "owners"
    assert configuration.get_collection_name(Company) == configuration.get_config().prefix + "companies"
    assert configuration.get_config().prefix == "async-default-test-"
    assert configuration.get_config().project == "async-default-test"
    assert configuration.get_config().name == "(default)"

    # Finding data from DB
    print(f"\nNumber of company owners with first name: 'John': {len(await Company.find({"owner.first_name": "John"}))}")

    print(f"\nNumber of companies with id: '1234567-8a': {len(await Company.find({"company_id": "1234567-8a"}))}")

    # Delete everything from the database
    await company.delete_all_for_model()
    deletion_success = [] == await Company.find({"company_id": "1234567-8a"})
    print(f"\nDeletion of (default) DB succeeded: {deletion_success}\n")




# Now with multiple ASYNC clients/dbs:
async def new_way():

    config_name = "companies"

    class Owner(AsyncModel):
        """Dummy owner Pydantic model."""
        __db_config__ = config_name
        __collection__ = "owners"
        first_name: str
        last_name: str


    class Company(AsyncModel):
        """Dummy company Firedantic model."""
        __db_config__ = config_name
        __collection__ = config_name
        company_id: str
        owner: Owner

    # 1. Add first config with config_name = "companies"
    configuration.add(
        name=config_name,
        prefix="async-companies-test-",
        project="async-companies-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Now you can use the model to save it to Firestore
    owner = Owner(first_name="Alice", last_name="Begone")
    company = Company(company_id="1234567-9", owner=owner)

    # Save the company/owner info to the DB  
    await company.save()  # only need to include config_name when not using default

    # Reloads model data from the database to ensure most-up-to-date info
    await company.reload()

    # #####################################################

    # 2. Add the second config with config_name = "billing"
    config_name = "billing"

    class BillingAccount(AsyncModel):
        """Dummy billing account Pydantic model."""
        __db_config__ = config_name
        __collection__ = "accounts"
        name: str
        billing_id: int
        owner: str


    class BillingCompany(AsyncModel):
        """Dummy company Firedantic model."""
        __db_config__ = config_name
        __collection__ = "companies"
        company_id: str
        billing_account: BillingAccount

    configuration.add(
        name=config_name,
        prefix="async-billing-test-",
        project="async-billing-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Assert that async clients exists and added configurations are correct
    assert isinstance(configuration.get_async_client("billing"), AsyncClient)

    assert configuration.get_collection_name(BillingAccount, "billing") == configuration.get_config("billing").prefix + "accounts"
    assert configuration.get_collection_name(BillingCompany, "billing") == configuration.get_config("billing").prefix + "companies"

    assert configuration.get_config("billing").prefix == "async-billing-test-"
    assert configuration.get_config("billing").project == "async-billing-test"
    assert configuration.get_config("billing").name == "billing"

    assert isinstance(configuration.get_async_client("companies"), AsyncClient)

    assert configuration.get_collection_name(Company, "companies") == configuration.get_config("companies").prefix + "companies"

    assert configuration.get_config("companies").prefix == "async-companies-test-"
    assert configuration.get_config("companies").project == "async-companies-test"
    assert configuration.get_config("companies").name == "companies"

    # Create and save billing account and billing company
    account = BillingAccount(name="ABC Billing", billing_id=801048, owner="MFisher")
    bc = BillingCompany(company_id="1234567-8c", billing_account=account)

    await account.save()
    await bc.save()

    # Reloads model data from the database
    await account.reload()
    await bc.reload()

    # 3. Finding data
    print(f"\nNumber of company owners with first name: 'Alice': {len(await Company.find({"owner.first_name": "Alice"}))}")

    print(f"\nNumber of billing companies with id: '1234567-8c': {len(await BillingCompany.find({"company_id": "1234567-8c"}))}")

    print(f"\nNumber of billing accounts with billing_id: 801048: {len(await BillingCompany.find({"billing_account.billing_id": 801048}))}")

    # Delete everything from the database
    await company.delete_all_for_model()
    await bc.delete_all_for_model()

    deletion_success = [] == await Company.find({"company_id": "1234567-8a"})
    print(f"\nDeletion of 'companies' DB succeeded: {deletion_success}")

    deletion_success = [] == await BillingCompany.find({"billing_account.billing_id": 801048})
    print(f"\nDeletion of 'billing' DB succeeded: {deletion_success}")



# suppress silent error msg from asyncio threads
def dbg_hook(exctype, value, tb):
    print("=== Uncaught exception ===")
    print(exctype, value)
    import traceback
    traceback.print_tb(tb)

sys.excepthook = dbg_hook

if __name__ == "__main__":
    import asyncio

    print("\n---- Running OLD way ----")
    asyncio.run(old_way())

    print("\n---- Running NEW way ----")
    asyncio.run(new_way())





