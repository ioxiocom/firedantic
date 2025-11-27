from os import environ
from unittest.mock import Mock

import google.auth.credentials
from google.cloud.firestore import AsyncClient, Client

from firedantic import Configuration, configure, CONFIGURATIONS
from billing_models import BillingAccount, BillingCompany
from base_models import MyModel


## OLD WAY:
def configure_sync_client():
    # Firestore emulator must be running if using locally.
    if environ.get("FIRESTORE_EMULATOR_HOST"):
        client = Client(
            project="firedantic-test",
            credentials=Mock(spec=google.auth.credentials.Credentials),
        )
    else:
        client = Client()

    configure(client, prefix="firedantic-sync-")
    assert CONFIGURATIONS["prefix"] == "firedantic-sync-"
    assert isinstance(CONFIGURATIONS["db"], Client)


def configure_async_client():
    # Firestore emulator must be running if using locally.
    if environ.get("FIRESTORE_EMULATOR_HOST"):
        client = AsyncClient(
            project="firedantic-test",
            credentials=Mock(spec=google.auth.credentials.Credentials),
        )
    else:
        client = AsyncClient()

    configure(client, prefix="firedantic-async-")
    assert CONFIGURATIONS["prefix"] == "firedantic-async-"
    assert isinstance(CONFIGURATIONS["db"], AsyncClient)



## NEW WAY:
def configure_multiple_clients():
    config = Configuration()

    # name = (default)
    config.add(
        prefix="firedantic-test-",
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # name = billing
    config.add(
        name="billing",
        prefix="test-billing-",
        project="test-billing",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    default = config.get_config() ## pulls default config
    print(config.get_collection_ref(MyModel))

    assert default.prefix == "firedantic-test-"
    assert isinstance(config.get_client(), Client)

    billing = config.get_config("billing") ## pulls billing config
    assert billing.prefix == "test-billing-"

    print(config.get_collection_ref(BillingAccount, "billing"))
    assert isinstance(config.get_client("billing"), Client)

    print(config.get_async_collection_ref(BillingAccount, "billing"))
    assert isinstance(config.get_async_client("billing"), AsyncClient)

print("\n---- Running OLD way ----")
configure_sync_client()
configure_async_client()
print("\n---- Running NEW way ----")
configure_multiple_clients()
