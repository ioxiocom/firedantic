from os import environ
from typing import Any, Dict, Optional, Type, Union

from google.auth.credentials import Credentials
from google.cloud.firestore_v1 import (
    AsyncClient, 
    AsyncTransaction, 
    Client, 
    CollectionReference,
    Transaction
)
from pydantic import BaseModel

# --- Old compatibility surface (kept for backwards compatibility) ---
CONFIGURATIONS: Dict[str, Any] = {}

def configure(client: Union[Client, AsyncClient], prefix: str = "") -> None:
    """
    Legacy helper: updates the module-level `configuration` default entry and preserves
    the old CONFIGURATIONS mapping so old callers continue to work.
    Configures the prefix and DB.
    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    if isinstance(client, AsyncClient):
        configuration.add(name="(default)", prefix=prefix, async_client=client)
    else:
        # treat as sync client
        configuration.add(name="(default)", prefix=prefix, client=client)
    
    CONFIGURATIONS["db"] = client
    CONFIGURATIONS["prefix"] = prefix


def get_transaction() -> Transaction:
    """Backward-compatible transaction getter (sync)."""
    return configuration.get_transaction()


def get_async_transaction() -> AsyncTransaction:
    """Backward-compatible async transaction getter."""
    return configuration.get_async_transaction()


# --- New configuration system ---
class ConfigItem(BaseModel):
    """
    Holds configuration for a named Firestore connection.
    Use arbitrary_types_allowed so we can store Client/AsyncClient/Credentials objects.
    """
    name: str
    prefix: str
    project: Optional[str] = None
    credentials: Optional[Credentials] = None
    client: Optional[Any] = None
    async_client: Optional[Any] = None

    model_config = {"arbitrary_types_allowed": True}

class Configuration:
    """
    Registry for named Firestore configurations.

    Usage Example:
        configuration.add(name="billing", project="myproj", credentials=creds)
        client = configuration.get_client("billing")
    """

    def __init__(self) -> None:
        
        # mapping name -> ConfigItem
        self.config: Dict[str, ConfigItem] = {}

        # Create a sensible default config entry, but avoid passing empty string as project.
        default_project = environ.get("GOOGLE_CLOUD_PROJECT") or None
        
        self.config["(default)"] = ConfigItem(
            name="(default)",
            prefix="",
            project=default_project,
            credentials=None,
            client=None,
            async_client=None
        )
    
    # dict-like accessors
    def __getitem__(self, name: str) -> ConfigItem:
        return self.get_config(name)

    def __contains__(self, name: str) -> bool:
        return name in self.config
    
    def get(self, name: str, default=None):
        return self.config.get(name, default)

    def get_config(self, name: str = "(default)") -> ConfigItem:
        try:
            return self.config[name]
        except KeyError as err:
            raise KeyError(
                f"Configuration '{name}' not found. Available: {list(self.config.keys())}"
            ) from err
        
    def _normalize_project(self, project: Optional[str]) -> Optional[str]:
        """
        Convert empty-string project to None so Client(...) doesn't get empty string for project (i.e. project="")
        """
        if project:
            return project
        return environ.get("GOOGLE_CLOUD_PROJECT") or None


    """
    Add a named configuration.

    You may either pass pre-built client and/or async_client,
    or provide only project/credentials so clients will be constructed here.
    """
    def add(
        self,
        name: str = "(default)",  # adding a config without a name results in overriding the default
        prefix: str = "",
        project: Optional[str] = None,
        credentials: Optional[Credentials] = None,
        client: Optional[Client] = None,
        async_client: Optional[AsyncClient] = None,
    ) -> ConfigItem:
        
        normalized_project = self._normalize_project(project)
        
        # Construct clients lazily, only when they were not supplied
        if client is None and normalized_project is not None:
            client = Client(project=normalized_project, credentials=credentials)
        if async_client is None and normalized_project is not None:
            async_client = AsyncClient(project=normalized_project, credentials=credentials)

        item = ConfigItem(
            name=name,
            prefix=prefix,
            project=normalized_project,
            credentials=credentials,
            client=client,
            async_client=async_client,
        )
        self.config[name] = item
        return item

    # client accessors (lazy-check and raise errors)
    def get_client(self, name: Optional[str] = None) -> Client:
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
        if cfg.client is None:
            # give a clear error; tests should register a mock client or provide a project
            raise RuntimeError(
                f"No sync client configured for config '{resolved}'. "
                "Call configuration.add(..., client=...) or set GOOGLE_CLOUD_PROJECT and let add() build the client."
            )
        return cfg.client
    
    def get_async_client(self, name: Optional[str] = None) -> AsyncClient:
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
        if cfg.async_client is None:
            raise RuntimeError(
                f"No async client configured for config '{resolved}'. "
                "Call configuration.add(..., async_client=...) or set GOOGLE_CLOUD_PROJECT and let add() build the client."
            )
        return cfg.async_client

    def get_transaction(self, name: Optional[str] = None) -> Transaction:
        return self.get_client(name=name).transaction()

    def get_async_transaction(self, name: Optional[str] = None) -> AsyncTransaction:
        return self.get_async_client(name=name).transaction()
    
    # helpers for models to derive collection name / reference
    def get_collection_name(self, model_class: Type, config_name: Optional[str] = None) -> str:
        """
        Return the collection name string (prefix + model name).
        """
        resolved = config_name if config_name is not None else "(default)"
        cfg = self.get_config(resolved)
        prefix = cfg.prefix or ""
        
        if hasattr(model_class, "__collection__"):
            return prefix + model_class.__collection__
        else:
            model_name = model_class.__name__
            return f"{prefix}{model_name[0].lower()}{model_name[1:]}"  # (lower case first letter of model name)

    def get_collection_ref(self, model_class: Type, name: Optional[str] = None) -> CollectionReference:
        """
        Return a CollectionReference for the given model_class using the sync client.
        """
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
        client = cfg.client
        if client is None:
            raise RuntimeError(f"No sync client configured for config '{resolved}'")
        collection_name = self.get_collection_name(model_class, resolved)
        return client.collection(collection_name)

    def get_async_collection_ref(self, model_class: Type, name: Optional[str] = None):
        """
        Return an AsyncCollectionReference using the async client.
        """
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
        async_client = cfg.async_client
        if async_client is None:
            raise RuntimeError(f"No async client configured for config '{resolved}'")
        collection_name = self.get_collection_name(model_class, resolved)
        return async_client.collection(collection_name)
    
# make the module-level singleton available to models/tests
# other modules should: from firedantic.configurations import configuration
configuration = Configuration()
