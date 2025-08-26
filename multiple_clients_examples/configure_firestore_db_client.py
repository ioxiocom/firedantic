from os import environ
from unittest.mock import Mock

import google.auth.credentials
from google.cloud.firestore import AsyncClient, Client

from firedantic import Configuration, configure


## OLD WAY:
def configure_client():
    # Firestore emulator must be running if using locally.
    if environ.get("FIRESTORE_EMULATOR_HOST"):
        client = Client(
            project="firedantic-test",
            credentials=Mock(spec=google.auth.credentials.Credentials),
        )
    else:
        client = Client()

    configure(client, prefix="firedantic-test-")
    print(client)


def configure_async_client():
    # Firestore emulator must be running if using locally.
    if environ.get("FIRESTORE_EMULATOR_HOST"):
        client = AsyncClient(
            project="firedantic-test",
            credentials=Mock(spec=google.auth.credentials.Credentials),
        )
    else:
        client = AsyncClient()

    configure(client, prefix="firedantic-test-")
    print(client)


## NEW WAY:
def configure_multiple_clients():
    config = Configuration()

    # name = (default)
    config.create(
        prefix="firedantic-test-",
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    # name = billing
    config.create(
        name="billing",
        prefix="test-billing-",
        project="test-billing",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )

    print(config.get_client())  ## will pull the default client
    print(config.get_client("billing"))  ## will pull the billing client
    print(config.get_async_client("billing"))  ## will pull the billing async client


# print("\n---- Running OLD way ----")
# configure_client()
# configure_async_client()
# print("\n---- Running NEW way ----")
# configure_multiple_clients()
