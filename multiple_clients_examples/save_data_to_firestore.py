from unittest.mock import Mock

import google.auth.credentials
from billing_models import BillingAccount, BillingCompany
from company_models import Company, Owner
from configure_firestore_db_client import configure_client

from firedantic import Configuration


## With single client
def old_way():
    # Firestore emulator must be running if using locally.
    configure_client()

    # Now you can use the model to save it to Firestore
    owner = Owner(first_name="John", last_name="Doe")
    company = Company(company_id="1234567-8", owner=owner)
    company.save()

    # Prints out the firestore ID of the Company model
    print(f"\nFirestore ID: {company.id}")

    # Reloads model data from the database
    company.reload()


## Now with multiple clients/dbs:
def new_way():
    config = Configuration()

    # 1. Create first config with config_name = "(default)"
    config.create(
        prefix="firedantic-test-",
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Now you can use the model to save it to Firestore
    owner = Owner(first_name="Alice", last_name="Begone")
    company = Company(company_id="1234567-9", owner=owner)
    company.save()  # will use 'default' as config name

    # Reloads model data from the database
    company.reload()  # with no name supplied, config refers to "(default)"

    # 2. Create the second config with config_name = "billing"
    config_name = "billing"
    config.create(
        name=config_name,
        prefix="test-billing-",
        project="test-billing",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # Now you can use the model to save it to Firestore
    account = BillingAccount(name="ABC Billing", billing_id="801048", owner="MFisher")
    bc = BillingCompany(company_id="1234567-8", billing_account=account)

    bc.save(config_name)

    # Reloads model data from the database
    bc.reload(config_name)  # with config name supplied, config refers to "billing"

    # 3. Finding data
    # Can retrieve info from either database/client
    # When config is not specified, it will default to '(default)' config
    # The models do not know which config you intended to use them for, and they
    # could be used for a multitude of configurations at once.
    print(Company.find({"owner.first_name": "Alice"}))

    print(BillingCompany.find({"company_id": "1234567-8"}, config=config_name))

    print(
        BillingCompany.find(
            {"billing_account.billing_id": "801048"}, config=config_name
        )
    )


print("\n---- Running OLD way ----")
old_way()
print("\n---- Running NEW way ----")
new_way()
