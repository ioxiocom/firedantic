from os import environ
from typing import Any, Dict, Optional, Union

from google.auth.credentials import Credentials
from google.cloud.firestore_v1 import AsyncClient, AsyncTransaction, Client, Transaction
from pydantic import BaseModel

""" Old Way """
CONFIGURATIONS: Dict[str, Any] = {}

def configure(client: Union[Client, AsyncClient], prefix: str = "") -> None:
    """Configures the prefix and DB.
    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    global CONFIGURATIONS
    CONFIGURATIONS["db"] = client
    CONFIGURATIONS["prefix"] = prefix


def get_transaction() -> Transaction:
    """
    Get a new Firestore transaction for the configured client.
    """
    transaction = CONFIGURATIONS["db"].transaction()
    assert isinstance(transaction, Transaction)
    return transaction


def get_async_transaction() -> AsyncTransaction:
    """
    Get a new async Firestore transaction for the configured client.
    """
    transaction = CONFIGURATIONS["db"].transaction()
    assert isinstance(transaction, AsyncTransaction)
    return transaction

""" New Way """
class ConfigItem(BaseModel):
    prefix: str
    project: str = None
    credentials: Optional[Credentials] = None
    client: Optional[Client] = None
    async_client: Optional[AsyncClient] = None

    model_config = {
        "arbitrary_types_allowed": True
    }

class Configuration:
    def __init__(self):
        self.config: Dict[str, ConfigItem] = {
            "(default)": ConfigItem(
                name="(default)",
                prefix="",
                project=environ.get("GOOGLE_CLOUD_PROJECT", ""),
                credentials=None,
                client=Client(
                    project=environ.get("GOOGLE_CLOUD_PROJECT", ""),
                    credentials=None,
                ),
                async_client=AsyncClient(
                    project=environ.get("GOOGLE_CLOUD_PROJECT", ""),
                    credentials=None,           
                ),
            )
        }

    """
    Add a named configuration.

    You may either pass pre-built client and/or async_client,
    or provide only project/credentials so clients will be constructed here.
    """
    def add(
        self,
        name: str = "(default)",  # adding a config without a name results in overriding the default
        prefix: str = "",
        project: str = "",
        credentials: Optional[Credentials] = None,
        client: Optional[Client] = None,
        async_client: Optional[AsyncClient] = None,
    ) -> ConfigItem:
        # Construct clients only if they were not supplied
        if client is None:
            client = Client(project=project, credentials=credentials)
        if async_client is None:
            async_client = AsyncClient(project=project, credentials=credentials)

        item = ConfigItem(
            prefix=prefix,
            project=project,
            credentials=credentials,
            client=client,
            async_client=async_client,
        )
        self.config[name] = item
        return item
    
    def get_config_name(self, name: str = "(default)") -> ConfigItem:
        try:
            return self.config[name]
        except KeyError as err:
            raise KeyError(
                f"Configuration '{name}' not found. Available: {list(self.config.keys())}"
            ) from err

    """
    Resolve None -> "(default)" for clients since one may pass None to indicate default,
    the same follows for transactions.
    """
    def get_client(self, name: Optional[str] = None) -> Client:
        resolved = name if name is not None else "(default)"
        return self.get_config_name(resolved).client
    
    def get_async_client(self, name: Optional[str] = None) -> AsyncClient:
        resolved = name if name is not None else "(default)"
        return self.get_config_name(resolved).async_client

    def get_transaction(self, name: Optional[str] = None) -> Transaction:
        return self.get_client(name=name).transaction()

    def get_async_transaction(self, name: Optional[str] = None) -> AsyncTransaction:
        return self.get_async_client(name=name).transaction()
