from os import environ
from typing import Dict, Optional, Union

from google.auth.credentials import Credentials
from google.cloud.firestore_v1 import AsyncClient, AsyncTransaction, Client, Transaction
from pydantic import BaseModel


# for added support of multiple configurations/clients
class ConfigItem(BaseModel):
    prefix: str
    project: str = None
    credentials: Optional[Credentials] = None
    client: Optional[Client] = None
    async_client: Optional[AsyncClient] = None

    class Config:
        arbitrary_types_allowed = True


# updating CONFIGURATIONS dict to be able to contain many/multiple configurations
CONFIGURATIONS: Dict[str, ConfigItem] = {}


def get_client(proj, creds) -> Union[Client, AsyncClient]:
    # Firestore emulator must be running if using locally.
    if environ.get("FIRESTORE_EMULATOR_HOST"):
        client = Client(project=proj, credentials=creds)
    else:
        client = Client()

    return client


# Allow configure method to work as it was for backwards compatibility.
def configure(
    db: Union[Client, AsyncClient] = None,
    prefix: str = "",
) -> None:
    """Configures the prefix and DB.

    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    global CONFIGURATIONS
    CONFIGURATIONS["(default)"] = ConfigItem

    if isinstance(db, Client):
        CONFIGURATIONS["(default)"].client = db
    elif isinstance(db, AsyncClient):
        CONFIGURATIONS["(default)"].async_client = db
    CONFIGURATIONS["(default)"].prefix = prefix
    # other params get set to None by default


def get_transaction(config: str = "(default)") -> Transaction:
    """
    Get a new Firestore transaction for the configured client.
    """
    transaction = CONFIGURATIONS[config].client.transaction()
    assert isinstance(transaction, Transaction)
    return transaction


def get_async_transaction(config: str = "(default)") -> AsyncTransaction:
    """
    Get a new async Firestore transaction for the configured client.
    """
    transaction = CONFIGURATIONS[config].async_client.transaction()
    assert isinstance(transaction, AsyncTransaction)
    return transaction


class Configuration:
    def __init__(self):
        self.configurations: Dict[str, ConfigItem] = {}

    def create(
        self,
        name: str = "(default)",
        prefix: str = "",
        project: str = "",
        credentials: Credentials = None,
    ) -> None:
        self.configurations[name] = ConfigItem(
            prefix=prefix,
            project=project,
            credentials=credentials,
            client=Client(
                project=project,
                credentials=credentials,
            ),
            async_client=AsyncClient(
                project=project,
                credentials=credentials,
            ),
        )
        # add to global CONFIGURATIONS
        global CONFIGURATIONS
        CONFIGURATIONS[name] = self.configurations[name]

    def get_client(self, name: str = "(default)") -> Client:
        return self.configurations[name].client

    def get_async_client(self, name: str = "(default)") -> AsyncClient:
        return self.configurations[name].async_client

    def get_transaction(self, name: str = "(default)") -> Transaction:
        return self.get_client(name=name).transaction()

    def get_async_transaction(self, name: str = "(default)") -> AsyncTransaction:
        return self.get_async_client(name=name).transaction()
