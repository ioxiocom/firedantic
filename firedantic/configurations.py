from typing import Dict, Union

from google.cloud.firestore_v1 import AsyncClient, Client
from pydantic import BaseModel


class Configuration(BaseModel):
    """
    Defines a single configuration.
    """

    db: Union[Client, AsyncClient]
    prefix: str = ""


class ConfigurationDict(dict):
    """
    A dictionary-like object to handle multiple configurations with backward compatibility.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def __setitem__(self, key, value):
        if key in ("db", "prefix"):
            raise ValueError(f"Cannot create configuration named '{key}'.")
        super().__setitem__(key, value)

    def __getitem__(self, key):
        if "default" not in self or not self["default"] is None:
            raise ValueError(
                "No default configuration found. Run `configure` to get started."
            )
        if key == "db":
            return self["default"]
        if key == "prefix":
            return self["default"].prefix
        return super().__getitem__(key)


CONFIGURATIONS: Dict[str, Configuration] = ConfigurationDict()


def configure(db: Union[Client, AsyncClient], prefix: str = "") -> None:
    """
    Configures the prefix and DB.

    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    global CONFIGURATIONS  # pylint: disable=global-statement,global-variable-not-assigned

    # CONFIGURATIONS["db"] = db
    # CONFIGURATIONS["prefix"] = prefix

    configuration = Configuration(db=db, prefix=prefix)

    CONFIGURATIONS["default"] = configuration
