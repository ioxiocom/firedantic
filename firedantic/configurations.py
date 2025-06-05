from typing import Any, Dict, Union

from google.cloud.firestore_v1 import AsyncClient, AsyncTransaction, Client, Transaction

CONFIGURATIONS: Dict[str, Any] = {}


def configure(db: Union[Client, AsyncClient], prefix: str = "") -> None:
    """Configures the prefix and DB.

    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    global CONFIGURATIONS

    CONFIGURATIONS["db"] = db
    CONFIGURATIONS["prefix"] = prefix


def get_transaction() -> Transaction:
    """
    Get a new Firestore transaction for the configured DB.
    """
    transaction = CONFIGURATIONS["db"].transaction()
    assert isinstance(transaction, Transaction)
    return transaction


def get_async_transaction() -> AsyncTransaction:
    """
    Get a new Firestore transaction for the configured DB.
    """
    transaction = CONFIGURATIONS["db"].transaction()
    assert isinstance(transaction, AsyncTransaction)
    return transaction
