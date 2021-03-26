from abc import ABC
from typing import Any, List, Optional, Type, TypeVar, Union

import pydantic
from google.cloud.firestore_v1 import AsyncCollectionReference, AsyncDocumentReference
from google.cloud.firestore_v1.base_query import BaseQuery

from firedantic.configurations import CONFIGURATIONS
from firedantic.exceptions import CollectionNotDefined, ModelNotFoundError

TAsyncModel = TypeVar("TAsyncModel", bound="AsyncModel")

# https://firebase.google.com/docs/firestore/query-data/queries#query_operators
FIND_TYPES = {
    "<",
    "<=",
    "==",
    ">",
    ">=",
    "!=",
    "array-contains",
    "array-contains-any",
    "in",
    "not-in",
}


class AsyncModel(pydantic.BaseModel, ABC):
    """Base model class.

    Implements basic functionality for Pydantic models, such as save, delete, find etc.
    """

    __collection__: Optional[str] = None

    id: Optional[str] = None

    async def save(self) -> None:
        """Saves this model in the database."""
        data = self.dict(by_alias=True)
        if "id" in data:
            del data["id"]

        doc_ref = self._get_doc_ref()
        await doc_ref.set(data)
        self.id = doc_ref.id

    async def delete(self) -> None:
        """Deletes this model from the database."""
        await self._get_doc_ref().delete()

    @classmethod
    async def find(cls: Type[TAsyncModel], filter_: dict) -> List[TAsyncModel]:
        """Returns a list of models from the database based on a filter.

        Example: `Company.find({"company_id": "1234567-8"})`.
        Example: `Product.find({"stock": {">=": 1}})`.

        :param filter_: The filter criteria.
        :return: List of found models.
        """
        coll = cls._get_col_ref()

        query: Union[BaseQuery, AsyncCollectionReference] = coll

        for key, value in filter_.items():
            query = cls._add_filter(query, key, value)

        return [
            cls(id=doc_id, **doc_dict)
            async for doc_id, doc_dict in (
                (doc.id, doc.to_dict()) async for doc in query.stream()
            )
            if doc_dict is not None
        ]

    @classmethod
    def _add_filter(
        cls, query: Union[BaseQuery, AsyncCollectionReference], field: str, value: Any
    ) -> Union[BaseQuery, AsyncCollectionReference]:
        if type(value) is dict:
            for f_type in value:
                if f_type not in FIND_TYPES:
                    raise ValueError(
                        f"Unsupported filter type: {f_type}. Supported types are: {', '.join(FIND_TYPES)}"
                    )
                query = query.where(field, f_type, value[f_type])
            return query
        else:
            return query.where(field, "==", value)

    @classmethod
    async def find_one(cls: Type[TAsyncModel], filter_: dict) -> TAsyncModel:
        """Returns one model from the DB based on a filter.

        :param filter_: The filter criteria.
        :return: The model instance.
        :raise ModelNotFoundError: If the entry is not found.
        """
        models = await cls.find(filter_)
        try:
            return models[0]
        except IndexError:
            raise ModelNotFoundError(f"No '{cls.__name__}' found")

    @classmethod
    async def get_by_id(cls: Type[TAsyncModel], id_: str) -> TAsyncModel:
        """Returns a model based on the ID.

        :param id_: The id of the entry.
        :return: The model.
        :raise ModelNotFoundError: Raised if no matching document is found.
        """
        document = await cls._get_col_ref().document(id_).get()  # type: ignore
        data = document.to_dict()
        if data is None:
            raise ModelNotFoundError(f"No '{cls.__name__}' found with id '{id_}'")
        data["id"] = id_
        return cls(**data)

    @classmethod
    async def truncate_collection(cls, batch_size: int = 128) -> int:
        """Removes all documents inside a collection.

        :param batch_size: Batch size for listing documents.
        :return: Number of removed documents.
        """
        count = 0
        col_ref = cls._get_col_ref()

        while True:
            deleted = 0
            async for doc in col_ref.limit(batch_size).stream():  # type: ignore
                await doc.reference.delete()
                deleted += 1

            count += deleted
            if deleted < batch_size:
                return count

    @classmethod
    def _get_col_ref(cls) -> AsyncCollectionReference:
        """Returns the collection reference."""
        if cls.__collection__ is None:
            raise CollectionNotDefined(f"Missing collection name for {cls.__name__}")
        collection: AsyncCollectionReference = CONFIGURATIONS["db"].collection(
            CONFIGURATIONS["prefix"] + cls.__collection__
        )
        return collection

    def _get_doc_ref(self) -> AsyncDocumentReference:
        """Returns the document reference."""
        return self._get_col_ref().document(self.id)  # type: ignore
