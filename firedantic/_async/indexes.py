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

from firedantic._async.model import AsyncBareModel, IndexDef, IndexField
from firedantic._async.ttl_policy import set_up_ttl_policies

logger = getLogger("firedantic")


async def list_existing_indexes(
    client: FirestoreAdminAsyncClient, path: str
) -> Set[IndexDef]:
    """
    List existing database indexes and return a set of them
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
        query_scope = raw_index.query_scope.name
        fields = tuple(
            IndexField(name=f.field_path, order=f.order.name)
            for f in raw_index.fields
            if f.field_path != "__name__"
        )
        indexes.add(IndexDef(query_scope=query_scope, fields=fields))
    return indexes


async def create_compose_index(
    client: FirestoreAdminAsyncClient,
    index: IndexDef,
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
    gcloud_project: str,
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
        if not model.__composite_indexes__:
            continue
        path = (
            f"projects/{gcloud_project}/databases/{database}/"
            f"collectionGroups/{model.__collection__}"
        )
        indexes_in_db = await list_existing_indexes(client, path=path)
        model_indexes = set(model.__composite_indexes__)
        existing_indexes = indexes_in_db.intersection(model_indexes)
        new_indexes = model_indexes.difference(indexes_in_db)

        for index in existing_indexes:
            log_str = "Composite index already exists in DB: %s, collection: %s"
            logger.debug(log_str, index, model.get_collection_name())

        for index in new_indexes:
            log_str = "Creating new composite index: %s, collection: %s"
            logger.info(log_str, index, model.get_collection_name())
            operation = await create_compose_index(client, index, path)
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
    ops = await set_up_composite_indexes(gcloud_project, models, database, client)
    ops.extend(await set_up_ttl_policies(gcloud_project, models, database, client))
    return ops
