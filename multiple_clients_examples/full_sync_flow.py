from unittest.mock import Mock

# from pydantic import BaseModel
from firedantic import Model
from firedantic.configurations import configuration, Client

import google.auth.credentials


## With single sync client
def old_way():
    
    class Owner(Model):
        """Dummy owner Pydantic model."""
        __collection__ = "owners"
        first_name: str
        last_name: str


    class Company(Model):
        """Dummy company Firedantic model."""
        __collection__ = "companies"
        company_id: str
        owner: Owner
    
    # Firestore emulator must be running if using locally, name defaults to "(default)"
    configuration.add(
        prefix="sync-default-test-",
        project="sync-default-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Now you can use the model to save it to Firestore
    owner = Owner(first_name="John", last_name="Doe")
    company = Company(company_id="1234567-8", owner=owner)

    # Save the company/owner info to the DB  
    company.save()

    # Reloads model data from the database to ensure most-up-to-date info
    company.reload()

    # Assert that sync client exists and configuration is correct
    assert isinstance(configuration.get_client(), Client)
    assert configuration.get_collection_name(Owner) == configuration.get_config().prefix + "owners"
    assert configuration.get_collection_name(Company) == configuration.get_config().prefix + "companies"
    assert configuration.get_config().prefix == "sync-default-test-"
    assert configuration.get_config().project == "sync-default-test"
    assert configuration.get_config().name == "(default)"
    
    # Finding data from DB
    print(f"\nNumber of company owners with first name: 'John': {len(Company.find({"owner.first_name": "John"}))}")

    print(f"\nNumber of companies with id: '1234567-8': {len(Company.find({"company_id": "1234567-8"}))}")


    # Delete everything from the database
    company.delete_all_for_model()

# Now with multiple SYNC clients/dbs:
def new_way():

    config_name = "companies"

    class Owner(Model):
        """Dummy owner Pydantic model."""
        __db_config__ = config_name
        __collection__ = "owners"
        first_name: str
        last_name: str


    class Company(Model):
        """Dummy company Firedantic model."""
        __db_config__ = config_name
        __collection__ = config_name
        company_id: str
        owner: Owner

    # 1. Add first config with config_name = "companies"
    configuration.add(
        name=config_name,
        prefix="sync-companies-test-",
        project="sync-companies-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Now you can use the model to save it to Firestore
    owner = Owner(first_name="Alice", last_name="Begone")
    company = Company(company_id="1234567-9", owner=owner)

    company.save()

    # Reloads model data from the database
    company.reload()

    # #####################################################

    # 2. Add the second config with config_name = "billing"
    config_name = "billing"

    class BillingAccount(Model):
        """Dummy billing account Pydantic model."""
        __db_config__ = config_name
        __collection__ = "accounts"
        name: str
        billing_id: int
        owner: str


    class BillingCompany(Model):
        """Dummy company Firedantic model."""
        __db_config__ = config_name
        __collection__ = "companies"
        company_id: str
        billing_account: BillingAccount

    configuration.add(
        name=config_name,
        prefix="sync-billing-test-",
        project="sync-billing-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Assert that sync clients exists and added configurations are correct
    assert isinstance(configuration.get_client("billing"), Client)

    assert configuration.get_collection_name(BillingAccount, "billing") == configuration.get_config("billing").prefix + "accounts"
    assert configuration.get_collection_name(BillingCompany, "billing") == configuration.get_config("billing").prefix + "companies"

    assert configuration.get_config("billing").prefix == "sync-billing-test-"
    assert configuration.get_config("billing").project == "sync-billing-test"
    assert configuration.get_config("billing").name == "billing"

    assert isinstance(configuration.get_client("companies"), Client)

    assert configuration.get_collection_name(Company, "companies") == configuration.get_config("companies").prefix + "companies"

    assert configuration.get_config("companies").prefix == "sync-companies-test-"
    assert configuration.get_config("companies").project == "sync-companies-test"
    assert configuration.get_config("companies").name == "companies"


    # Create and save billing account and company
    account = BillingAccount(name="ABC Billing", billing_id=801048, owner="MFisher")
    bc = BillingCompany(company_id="1234567-8c", billing_account=account)

    account.save()
    bc.save()

    # Reloads model data from the database
    account.reload()
    bc.reload()

    # 3. Finding data
    print(f"\nNumber of company owners with first name: 'Alice': {len(Company.find({"owner.first_name": "Alice"}))}")

    print(f"\nNumber of billing companies with id: '1234567-8c': {len(BillingCompany.find({"company_id": "1234567-8c"}))}")

    print(f"\nNumber of billing accounts with billing_id: 801048: {len(BillingCompany.find({"billing_account.billing_id": 801048}))}")

    # now delete everything from the DBs:
    company.delete_all_for_model()
    bc.delete_all_for_model()




print("\n---- Running OLD way ----")
old_way()
print("\n---- Running NEW way ----")
new_way()


