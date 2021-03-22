from typing import Any, Dict, Union

from google.cloud.firestore_v1 import AsyncClient, Client

CONFIGURATIONS: Dict[str, Any] = {}


def configure(db: Union[Client, AsyncClient], prefix: str = "") -> None:
    """Configures the prefix and DB.

    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    global CONFIGURATIONS

    CONFIGURATIONS["db"] = db
    CONFIGURATIONS["prefix"] = prefix
