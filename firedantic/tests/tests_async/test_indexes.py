from unittest.mock import AsyncMock

from google.cloud.firestore import Query
from google.cloud.firestore_admin_v1 import ListIndexesResponse

from firedantic import (
    AsyncModel,
    async_set_up_composite_indexes,
    async_set_up_composite_indexes_and_ttl_policies,
    collection_group_index,
    collection_index,
)
from firedantic.tests.tests_async.conftest import MockListIndexOperation

import pytest  # noqa isort: skip


class BaseModelWithIndexes(AsyncModel):
    __collection__ = "modelWithIndexes"

    name: str
    status: int
    age: int


@pytest.mark.asyncio
async def test_set_up_composite_index(mock_admin_client):
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(("name", Query.ASCENDING), ("age", Query.DESCENDING)),
        )

    result = await async_set_up_composite_indexes(
        gcloud_project="proj",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1

    call_list = mock_admin_client.create_index.call_args_list
    # index is a protobuf structure sent via Google Cloud Admin
    path = call_list[0][1]["request"].parent
    assert path == "projects/proj/databases/(default)/collectionGroups/modelWithIndexes"
    index = call_list[0][1]["request"].index
    assert index.query_scope.name == "COLLECTION"
    assert len(index.fields) == 2
    assert index.fields[0].field_path == "name"
    assert index.fields[0].order.name == Query.ASCENDING
    assert index.fields[1].field_path == "age"
    assert index.fields[1].order.name == Query.DESCENDING


@pytest.mark.asyncio
async def test_set_up_collection_group_index(mock_admin_client):
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_group_index(
                ("name", Query.ASCENDING), ("age", Query.DESCENDING)
            ),
        )

    result = await async_set_up_composite_indexes(
        gcloud_project="proj",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1

    call_list = mock_admin_client.create_index.call_args_list
    # index is a protobuf structure sent via Google Cloud Admin
    path = call_list[0][1]["request"].parent
    assert path == "projects/proj/databases/(default)/collectionGroups/modelWithIndexes"
    index = call_list[0][1]["request"].index
    assert index.query_scope.name == "COLLECTION_GROUP"
    assert len(index.fields) == 2


@pytest.mark.asyncio
async def test_set_up_composite_indexes_and_policies(mock_admin_client):
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(("name", Query.ASCENDING), ("age", Query.DESCENDING)),
        )

    result = await async_set_up_composite_indexes_and_ttl_policies(
        gcloud_project="proj",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1

    call_list = mock_admin_client.create_index.call_args_list
    assert len(call_list) == 1


@pytest.mark.asyncio
async def test_set_up_many_composite_indexes(mock_admin_client):
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(("name", Query.ASCENDING), ("age", Query.DESCENDING)),
            collection_index(("age", Query.ASCENDING), ("status", Query.DESCENDING)),
            collection_index(
                ("age", Query.ASCENDING),
                ("status", Query.DESCENDING),
                ("name", Query.DESCENDING),
            ),
        )

    result = await async_set_up_composite_indexes(
        gcloud_project="fake-project",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 3


@pytest.mark.asyncio
async def test_existing_indexes_are_skipped(mock_admin_client):
    resp = ListIndexesResponse(
        {
            "indexes": [
                {
                    "name": (
                        "projects/fake-project/databases/(default)/collectionGroups/"
                        "modelWithIndexes/123456"
                    ),
                    "query_scope": "COLLECTION",
                    "fields": [
                        {"field_path": "name", "order": Query.ASCENDING},
                        {"field_path": "age", "order": Query.DESCENDING},
                        {"field_path": "__name__", "order": Query.ASCENDING},
                    ],
                },
                {
                    "name": (
                        "projects/fake-project/databases/(default)/collectionGroups/"
                        "modelWithIndexes/67889"
                    ),
                    "query_scope": "COLLECTION",
                    "fields": [
                        {"field_path": "age", "order": Query.ASCENDING},
                        {"field_path": "name", "order": Query.DESCENDING},
                        {"field_path": "__name__", "order": Query.ASCENDING},
                    ],
                },
            ]
        }
    )
    mock_admin_client.list_indexes = AsyncMock(
        return_value=MockListIndexOperation([resp])
    )

    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(("name", Query.ASCENDING), ("age", Query.DESCENDING)),
            collection_index(("age", Query.ASCENDING), ("name", Query.DESCENDING)),
        )

    result = await async_set_up_composite_indexes(
        gcloud_project="fake-project",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 0


@pytest.mark.asyncio
async def test_same_fields_in_another_collection(mock_admin_client):
    # Test that when another collection has an index with exactly the same fields,
    # it won't affect creating an index in the target collection
    resp = ListIndexesResponse(
        {
            "indexes": [
                {
                    "name": (
                        "projects/fake-project/databases/(default)/collectionGroups/"
                        "anotherModel/123456"
                    ),
                    "query_scope": "COLLECTION",
                    "fields": [
                        {"field_path": "name", "order": Query.ASCENDING},
                        {"field_path": "age", "order": Query.DESCENDING},
                        {"field_path": "__name__", "order": Query.ASCENDING},
                    ],
                },
            ]
        }
    )
    mock_admin_client.list_indexes = AsyncMock(
        return_value=MockListIndexOperation([resp])
    )

    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(("name", Query.ASCENDING), ("age", Query.DESCENDING)),
        )

    result = await async_set_up_composite_indexes(
        gcloud_project="fake-project",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1
