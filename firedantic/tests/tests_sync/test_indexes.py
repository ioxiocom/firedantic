from datetime import datetime
from unittest.mock import Mock

from google.cloud.firestore import Query
from google.cloud.firestore_admin_v1 import ListIndexesResponse

from firedantic import (
    CONFIGURATIONS,
    Model,
    collection_group_index,
    collection_index,
    set_up_composite_indexes,
    set_up_composite_indexes_and_ttl_policies,
)
from firedantic.common import IndexField
from firedantic.tests.tests_sync.conftest import MockListIndexOperation

import pytest  # noqa isort: skip


class BaseModelWithIndexes(Model):
    __collection__ = "modelWithIndexes"

    name: str
    status: int
    age: int


def test_set_up_composite_index(mock_admin_client) -> None:
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(
                IndexField("name", Query.ASCENDING),
                IndexField("age", Query.DESCENDING),
            ),
        )

    result = set_up_composite_indexes(
        gcloud_project="proj",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1

    call_list = mock_admin_client.create_index.call_args_list
    # index is a protobuf structure sent via Google Cloud Admin
    path = call_list[0][1]["request"].parent
    assert (
        path
        == f"projects/proj/databases/(default)/collectionGroups/{CONFIGURATIONS['prefix']}modelWithIndexes"
    )
    index = call_list[0][1]["request"].index
    assert index.query_scope.name == "COLLECTION"
    assert len(index.fields) == 2
    assert index.fields[0].field_path == "name"
    assert index.fields[0].order.name == Query.ASCENDING
    assert index.fields[1].field_path == "age"
    assert index.fields[1].order.name == Query.DESCENDING


def test_set_up_collection_group_index(mock_admin_client) -> None:
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_group_index(
                IndexField("name", Query.ASCENDING),
                IndexField("age", Query.DESCENDING),
            ),
        )

    result = set_up_composite_indexes(
        gcloud_project="proj",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1

    call_list = mock_admin_client.create_index.call_args_list
    # index is a protobuf structure sent via Google Cloud Admin
    path = call_list[0][1]["request"].parent
    assert (
        path
        == f"projects/proj/databases/(default)/collectionGroups/{CONFIGURATIONS['prefix']}modelWithIndexes"
    )
    index = call_list[0][1]["request"].index
    assert index.query_scope.name == "COLLECTION_GROUP"
    assert len(index.fields) == 2


def test_set_up_composite_indexes_and_policies(mock_admin_client) -> None:
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(
                IndexField("name", Query.ASCENDING),
                IndexField("age", Query.DESCENDING),
            ),
        )

        __ttl_field__ = "expire"
        expire: datetime

    result = set_up_composite_indexes_and_ttl_policies(
        gcloud_project="proj",
        models=(model for model in [ModelWithIndexes]),  # Test with a generator
        client=mock_admin_client,
    )
    assert len(result) == 2

    call_list = mock_admin_client.create_index.call_args_list
    assert len(call_list) == 1


def test_set_up_many_composite_indexes(mock_admin_client) -> None:
    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(
                IndexField("name", Query.ASCENDING),
                IndexField("age", Query.DESCENDING),
            ),
            collection_index(
                IndexField("age", Query.ASCENDING),
                IndexField("status", Query.DESCENDING),
            ),
            collection_index(
                IndexField("age", Query.ASCENDING),
                IndexField("status", Query.DESCENDING),
                IndexField("name", Query.DESCENDING),
            ),
        )

    result = set_up_composite_indexes(
        gcloud_project="fake-project",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 3


def test_set_up_indexes_model_without_indexes(mock_admin_client) -> None:
    class ModelWithoutIndexes(Model):
        __collection__ = "modelWithoutIndexes"

        name: str

    result = set_up_composite_indexes(
        gcloud_project="proj",
        models=[ModelWithoutIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 0

    call_list = mock_admin_client.create_index.call_args_list
    assert len(call_list) == 0


def test_existing_indexes_are_skipped(mock_admin_client) -> None:
    resp = ListIndexesResponse(
        {
            "indexes": [
                {
                    "name": (
                        "projects/fake-project/databases/(default)/collectionGroups/"
                        f"{CONFIGURATIONS['prefix']}modelWithIndexes/123456"
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
                        f"{CONFIGURATIONS['prefix']}modelWithIndexes/67889"
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
    mock_admin_client.list_indexes = Mock(return_value=MockListIndexOperation([resp]))

    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(
                IndexField("name", Query.ASCENDING),
                IndexField("age", Query.DESCENDING),
            ),
            collection_index(
                IndexField("age", Query.ASCENDING),
                IndexField("name", Query.DESCENDING),
            ),
        )

    result = set_up_composite_indexes(
        gcloud_project="fake-project",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 0


def test_same_fields_in_another_collection(mock_admin_client) -> None:
    # Test that when another collection has an index with exactly the same fields,
    # it won't affect creating an index in the target collection
    resp = ListIndexesResponse(
        {
            "indexes": [
                {
                    "name": (
                        "projects/fake-project/databases/(default)/collectionGroups/"
                        f"{CONFIGURATIONS['prefix']}anotherModel/123456"
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
    mock_admin_client.list_indexes = Mock(return_value=MockListIndexOperation([resp]))

    class ModelWithIndexes(BaseModelWithIndexes):
        __composite_indexes__ = (
            collection_index(
                IndexField("name", Query.ASCENDING),
                IndexField("age", Query.DESCENDING),
            ),
        )

    result = set_up_composite_indexes(
        gcloud_project="fake-project",
        models=[ModelWithIndexes],
        client=mock_admin_client,
    )
    assert len(result) == 1
