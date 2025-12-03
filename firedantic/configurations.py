from os import environ
from typing import Any, Dict, Optional, Type, Union

from google.auth.credentials import Credentials
from google.api_core.client_options import ClientOptions
from google.api_core.gapic_v1.client_info import ClientInfo
from google.cloud.firestore_v1 import (
    AsyncClient, 
    AsyncTransaction, 
    Client, 
    CollectionReference,
    Transaction
)
from google.cloud.firestore_admin_v1 import FirestoreAdminClient
from google.cloud.firestore_admin_v1.services.firestore_admin import FirestoreAdminAsyncClient
from google.cloud.firestore_admin_v1.services.firestore_admin.transports.base import DEFAULT_CLIENT_INFO
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
    Clients may be provided directly, or created lazily from the stored params.
    """
    name: str
    prefix: str = ""
    project: Optional[str] = None
    database: str = "(default)"

    # client objects (may be None; created lazily)
    client: Optional[Any] = None
    async_client: Optional[Any] = None
    admin_client: Optional[Any] = None
    async_admin_client: Optional[Any] = None

    # creation params (kept so we can lazily instantiate clients)
    credentials: Optional[Credentials] = None
    client_info: Optional[Any] = None
    client_options: Optional[Union[Dict[str, Any], Any]] = None
    admin_transport: Optional[Any] = None

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
            database="(default)",
        )

    def add(
        self,
        name: str = "(default)",  # adding a config without a name results in overriding the default
        *,
        project: Optional[str] = None,
        database: str = "(default)",
        prefix: str = "",
        client: Optional[Any] = None,
        async_client: Optional[Any] = None,
        admin_client: Optional[Any] = None,
        async_admin_client: Optional[Any] = None,
        credentials: Optional[Credentials] = None,
        client_info: Optional[Any] = None,
        client_options: Optional[Union[Dict[str, Any], Any]] = None,
        admin_transport: Optional[Any] = None,
    ) -> ConfigItem:
        """
        Add a named configuration.

        You may either pass a pre-built client and/or an async_client,
        or provide only project/credentials so clients will be constructed lazily.
        """
        
        normalized_project = self._normalize_project(project)
        
        # Construct clients lazily, only when they were not supplied
        # if client is None and normalized_project is not None:
        #     client = Client(project=normalized_project, credentials=credentials)
        # if async_client is None and normalized_project is not None:
        #     async_client = AsyncClient(project=normalized_project, credentials=credentials)

        item = ConfigItem(
            name=name,
            project=normalized_project,
            database=database,
            prefix=prefix,
            client=client,
            async_client=async_client,
            admin_client=admin_client,
            async_admin_client=async_admin_client,
            credentials=credentials,
            client_info=client_info,
            client_options=client_options,
            admin_transport=admin_transport,
        )
        self.config[name] = item
        return item
    
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
        
    def get_config_names(self):
        return list(self.config.keys())
        
    def _normalize_project(self, project: Optional[str]) -> Optional[str]:
        """
        Convert empty-string project to None so Client(...) doesn't get empty string for project (i.e. project="")
        """
        if project:
            return project
        return environ.get("GOOGLE_CLOUD_PROJECT") or None

    # sync client accessor (lazy-create)
    def get_client(self, name: Optional[str] = None) -> Client:
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
        if cfg.client is None:
            # don't try to create a client if we lack project info
            if cfg.project is None:
                raise RuntimeError(
                    f"No sync client configured for '{resolved}' and no project available; "
                    "call configuration.add(..., client=..., project=...) or set " \
                    "GOOGLE_CLOUD_PROJECT and let add() build the client."
                )
            cfg.client = Client(
                project=cfg.project,
                credentials=cfg.credentials,
                client_info=cfg.client_info,
                client_options=cfg.client_options,  # type: ignore[arg-type]
                # NOTE: modern firestore clients may accept database param in constructor; keep for future.
            )
        return cfg.client
    
    # async client accessor (lazy-create)
    def get_async_client(self, name: Optional[str] = None) -> AsyncClient:
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)

        if cfg.async_client is None:
            if cfg.project is None:
                raise RuntimeError(
                    f"No async client configured for '{resolved}' and no project available; "
                    "call configuration.add(..., async_client=..., project=...) or set " \
                    "GOOGLE_CLOUD_PROJECT and let add() build the client."
                )
            cfg.async_client = AsyncClient(
                project=cfg.project,
                credentials=cfg.credentials,
                client_info=cfg.client_info,
                client_options=cfg.client_options,  # type: ignore[arg-type]
            )
        return cfg.async_client
    
    # admin client accessor (lazy-create)
    def get_admin_client(self, name: Optional[str] = None) -> FirestoreAdminClient:
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
       
        if cfg.admin_client is None:
            cfg.admin_client = FirestoreAdminClient(
                credentials=cfg.credentials,
                transport=cfg.admin_transport,
                client_options=cfg.client_options,  # type: ignore[arg-type]
                client_info=cfg.client_info or DEFAULT_CLIENT_INFO,
            )
        return cfg.admin_client

    # async admin client accessor (lazy-create)
    def get_async_admin_client(self, name: Optional[str] = None) -> FirestoreAdminAsyncClient:
        resolved = name if name is not None else "(default)"
        cfg = self.get_config(resolved)
        
        if cfg.async_admin_client is None:
            cfg.async_admin_client = FirestoreAdminAsyncClient(
                credentials=cfg.credentials,
                transport=cfg.admin_transport,
                client_options=cfg.client_options,  # type: ignore[arg-type]
                client_info=cfg.client_info or DEFAULT_CLIENT_INFO,
            )
        return cfg.async_admin_client

    # transactions
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
