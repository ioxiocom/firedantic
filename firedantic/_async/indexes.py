from logging import getLogger
from typing import Iterable, List, Optional, Set, Type

from google.api_core.operation_async import AsyncOperation
from google.cloud.firestore_admin_v1 import (
    CreateIndexRequest,
    Index,
    ListIndexesRequest,
)
from google.cloud.firestore_admin_v1.services.firestore_admin import (
    FirestoreAdminAsyncClient,
)

from firedantic._async.model import AsyncBareModel
from firedantic._async.ttl_policy import set_up_ttl_policies
from firedantic.common import IndexDefinition, IndexField
from firedantic.configurations import configuration

logger = getLogger("firedantic")


async def get_existing_indexes(
    client: FirestoreAdminAsyncClient, path: str
) -> Set[IndexDefinition]:
    """
    Get existing database indexes and return a set of them
    for easy comparison with other indexes

    :param client: The Firestore admin client.
    :param path: Index path in Firestore.
    :return: Set of IndexDef tuples
    """
    raw_indexes = []
    request = ListIndexesRequest({"parent": path})
    operation = await client.list_indexes(request=request)
    async for page in operation.pages:
        raw_indexes.extend(list(page.indexes))

    indexes = set()
    for raw_index in raw_indexes:
        # apparently `list_indexes` returns all indexes in all collections
        if not raw_index.name.startswith(path):
            continue
        query_scope = raw_index.query_scope.name
        fields = tuple(
            IndexField(name=f.field_path, order=f.order.name)  # noqa
            for f in raw_index.fields
            if f.field_path != "__name__"
        )
        indexes.add(IndexDefinition(query_scope=query_scope, fields=fields))
    return indexes


async def create_composite_index(
    client: FirestoreAdminAsyncClient,
    index: IndexDefinition,
    path: str,
) -> AsyncOperation:
    """
    Create a composite index in Firestore

    :param client: The Firestore admin client.
    :param index: Index definition.
    :param path: Index path in Firestore.
    :return: Operation that was launched to create the index.
    """
    request = CreateIndexRequest(
        {
            "parent": path,
            "index": Index(
                {
                    "query_scope": index.query_scope,
                    "fields": [
                        {"field_path": field[0], "order": field[1]}
                        for field in list(index.fields)
                    ],
                }
            ),
        }
    )
    return await client.create_index(request=request)


async def set_up_composite_indexes(
    gcloud_project: Optional[str],
    models: Iterable[Type[AsyncBareModel]],
    database: str = "(default)",
    client: Optional[FirestoreAdminAsyncClient] = None,
) -> List[AsyncOperation]:
    """
    Set up composite indexes for models.

    :param gcloud_project: The technical name of the project in Google Cloud.
    :param models: Models for which to set up composite indexes.
    :param database: The Firestore database instance (it now supports multiple).
    :param client: The Firestore admin client.
    :return: List of operations that were launched to create indexes.
    """
    if not client:
        client = FirestoreAdminAsyncClient()

    operations = []
    for model in models:
        if not getattr(model, "__composite_indexes__", None):
            continue

        # Resolve config name: prefer model __db_config__ if present; else default
        config_name = getattr(model, "__db_config__", "(default)")

        # If caller did not pass gcloud_project, try to get it from config
        project = gcloud_project or configuration.get_config(config_name).project

        # Build collection group path using configuration helper (includes prefix)
        collection_group = configuration.get_collection_name(model, config_name=config_name)
        path = f"projects/{project}/databases/{database}/collectionGroups/{collection_group}"

        indexes_in_db = await get_existing_indexes(client, path=path)
        model_indexes = set(model.__composite_indexes__)
        existing_indexes = indexes_in_db.intersection(model_indexes)
        new_indexes = model_indexes.difference(indexes_in_db)

        for index in existing_indexes:
            logger.debug("Composite index already exists in DB: %s, collection: %s", index, collection_group)

        for index in new_indexes:
            logger.info("Creating new composite index: %s, collection: %s", index, collection_group)
            operation = await create_composite_index(client, index, path)
            operations.append(operation)

    return operations


async def set_up_composite_indexes_and_ttl_policies(
    gcloud_project: str,
    models: Iterable[Type[AsyncBareModel]],
    database: str = "(default)",
    client: Optional[FirestoreAdminAsyncClient] = None,
) -> List[AsyncOperation]:
    """
    Set up indexes and TTL policies that are defined in the model

    :param gcloud_project: The technical name of the project in Google Cloud.
    :param models: Models for which to set up composite indexes and TTL policies.
    :param database: The Firestore database instance (it now supports multiple).
    :param client: The Firestore admin client.
    :return: List of operations that were launched.
    """
    models = list(models)
    ops = await set_up_composite_indexes(gcloud_project, models, database, client)
    ops.extend(await set_up_ttl_policies(gcloud_project, models, database, client))
    return ops
