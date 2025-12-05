from os import environ
from unittest.mock import Mock

import google.auth.credentials
from google.cloud.firestore import AsyncClient, Client

from firedantic.configurations import configuration, configure, CONFIGURATIONS


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

    # ---- Assertions ----
    assert CONFIGURATIONS["prefix"] == "firedantic-sync-"
    assert isinstance(CONFIGURATIONS["db"], Client)

    # project check
    assert CONFIGURATIONS["db"].project == "firedantic-test"
    
    # emulator expectations
    assert isinstance(CONFIGURATIONS["db"]._credentials, Mock)

    # ensure no accidental async setting
    assert not isinstance(CONFIGURATIONS["db"], AsyncClient)



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

    # ---- Assertions ----
    assert CONFIGURATIONS["prefix"] == "firedantic-async-"
    assert isinstance(CONFIGURATIONS["db"], AsyncClient)

    # project check
    assert CONFIGURATIONS["db"].project == "firedantic-test"
    
    # emulator expectations
    assert isinstance(CONFIGURATIONS["db"]._credentials, Mock)

    # ensure no accidental async setting
    assert not isinstance(CONFIGURATIONS["db"], Client)



## NEW WAY:
def configure_multiple_clients():
    config = configuration

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


    # ===========================
    #   VALIDATE DEFAULT CONFIG
    # ===========================
    default = config.get_config()  # loads "(default)"

    # Basic prefix & project
    assert default.prefix == "firedantic-test-"
    assert default.project == "firedantic-test"

    # Client objects exist when called
    assert config.get_client() is not None
    assert config.get_async_client() is not None

    # Types are correct
    assert isinstance(default.client, Client)
    assert isinstance(default.async_client, AsyncClient)

    # Credentials are what we passed in
    assert isinstance(default.credentials, Mock)

    # Config can return correct client API
    assert isinstance(config.get_client(), Client)
    assert isinstance(config.get_async_client(), AsyncClient)


    # ===========================
    #   VALIDATE BILLING CONFIG
    # ===========================
    billing = config.get_config("billing")

    # Prefix & project
    assert billing.prefix == "test-billing-"
    assert billing.project == "test-billing"

    # Client objects exist when called
    assert config.get_client("billing") is not None
    assert config.get_async_client("billing") is not None

    # Correct client types
    assert isinstance(billing.client, Client)
    assert isinstance(billing.async_client, AsyncClient)

    # Correct credentials object
    assert isinstance(billing.credentials, Mock)

    # Ensure default and billing configs are distinct objects
    assert billing is not default

    # Make sure nothing leaked between configs
    assert billing.prefix != default.prefix
    assert billing.project != default.project



try:
    ### ---- Running OLD way ----
    configure_sync_client()
    configure_async_client()

    ### ---- Running NEW way ----
    configure_multiple_clients()
    
    print("\nAll configure_firestore_db_client tests passed!\n")

except AssertionError as e:
    print(f"\nconfigure_firestore_db_client tests failed: {e}\n")
    raise e
