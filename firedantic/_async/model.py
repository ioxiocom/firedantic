from abc import ABC
from logging import getLogger
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import pydantic
from google.cloud.firestore_v1 import (
    AsyncCollectionReference,
    AsyncDocumentReference,
    DocumentSnapshot,
)
from google.cloud.firestore_v1.async_query import AsyncQuery

import firedantic.operators as op
from firedantic import async_truncate_collection
from firedantic.configurations import CONFIGURATIONS
from firedantic.exceptions import CollectionNotDefined, ModelNotFoundError

TAsyncBareModel = TypeVar("TAsyncBareModel", bound="AsyncBareModel")
TAsyncBareSubModel = TypeVar("TAsyncBareSubModel", bound="AsyncBareSubModel")
logger = getLogger("firedantic")

# https://firebase.google.com/docs/firestore/query-data/queries#query_operators
FIND_TYPES = {
    op.LT,
    op.LTE,
    op.EQ,
    op.NE,
    op.GT,
    op.GTE,
    op.ARRAY_CONTAINS,
    op.ARRAY_CONTAINS_ANY,
    op.IN,
    op.NOT_IN,
}


def _get_col_ref(cls, name) -> AsyncCollectionReference:
    if name is None:
        raise CollectionNotDefined(f"Missing collection name for {cls.__name__}")

    collection: AsyncCollectionReference = CONFIGURATIONS["db"].collection(
        CONFIGURATIONS["prefix"] + name
    )
    return collection


class AsyncBareModel(pydantic.BaseModel, ABC):
    """Base model class.

    Implements basic functionality for Pydantic models, such as save, delete, find etc.
    """

    __collection__: Optional[str] = None
    __document_id__: str

    async def save(self) -> None:
        """Saves this model in the database."""
        data = self.dict(by_alias=True)
        if self.__document_id__ in data:
            del data[self.__document_id__]

        doc_ref = self._get_doc_ref()
        await doc_ref.set(data)
        setattr(self, self.__document_id__, doc_ref.id)

    async def delete(self) -> None:
        """Deletes this model from the database."""
        await self._get_doc_ref().delete()

    def get_document_id(self):
        """
        Get the document ID for this model instance
        """
        return getattr(self, self.__document_id__, None)

    @classmethod
    async def find(
        cls: Type[TAsyncBareModel], filter_: Optional[dict] = None
    ) -> List[TAsyncBareModel]:
        """Returns a list of models from the database based on a filter.

        Example: `Company.find({"company_id": "1234567-8"})`.
        Example: `Product.find({"stock": {">=": 1}})`.

        :param filter_: The filter criteria.
        :return: List of found models.
        """
        if not filter_:
            filter_ = {}

        query: Union[AsyncQuery, AsyncCollectionReference] = cls._get_col_ref()

        for key, value in filter_.items():
            query = cls._add_filter(query, key, value)

        def _cls(doc_id: str, data: Dict[str, Any]) -> TAsyncBareModel:
            if cls.__document_id__ in data:
                logger.warning(
                    "%s document ID %s contains conflicting %s in data with value %s",
                    cls.__name__,
                    doc_id,
                    cls.__document_id__,
                    data[cls.__document_id__],
                )
            data[cls.__document_id__] = doc_id
            model = cls(**data)
            setattr(model, cls.__document_id__, doc_id)
            return model

        return [
            _cls(doc_id, doc_dict)
            async for doc_id, doc_dict in (
                (doc.id, doc.to_dict()) async for doc in query.stream()  # type: ignore
            )
            if doc_dict is not None
        ]

    @classmethod
    def _add_filter(
        cls, query: Union[AsyncQuery, AsyncCollectionReference], field: str, value: Any
    ) -> Union[AsyncQuery, AsyncCollectionReference]:
        if type(value) is dict:
            for f_type in value:
                if f_type not in FIND_TYPES:
                    raise ValueError(
                        f"Unsupported filter type: {f_type}. Supported types are: {', '.join(FIND_TYPES)}"
                    )
                query: AsyncQuery = query.where(field, f_type, value[f_type])  # type: ignore
            return query
        else:
            query: AsyncQuery = query.where(field, "==", value)  # type: ignore
            return query

    @classmethod
    async def find_one(
        cls: Type[TAsyncBareModel], filter_: Optional[dict] = None
    ) -> TAsyncBareModel:
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
    async def get_by_doc_id(cls: Type[TAsyncBareModel], doc_id: str) -> TAsyncBareModel:
        """Returns a model based on the document ID.

        :param doc_id: The document ID of the entry.
        :return: The model.
        :raise ModelNotFoundError: Raised if no matching document is found.
        """

        if not doc_id:
            # Getting a document with doc_id set to an empty string would raise a
            # google.api_core.exceptions.InvalidArgument exception.
            raise ModelNotFoundError(
                f"No '{cls.__name__}' found with {cls.__document_id__} '{doc_id}'"
            )

        document: DocumentSnapshot = await cls._get_col_ref().document(doc_id).get()  # type: ignore
        data = document.to_dict()
        if data is None:
            raise ModelNotFoundError(
                f"No '{cls.__name__}' found with {cls.__document_id__} '{doc_id}'"
            )
        data[cls.__document_id__] = doc_id
        model = cls(**data)
        setattr(model, cls.__document_id__, doc_id)
        return model

    @classmethod
    async def truncate_collection(cls, batch_size: int = 128) -> int:
        """Removes all documents inside a collection.

        :param batch_size: Batch size for listing documents.
        :return: Number of removed documents.
        """
        return await async_truncate_collection(
            col_ref=cls._get_col_ref(),
            batch_size=batch_size,
        )

    @classmethod
    def _get_col_ref(cls) -> AsyncCollectionReference:
        """Returns the collection reference."""
        return _get_col_ref(cls, cls.__collection__)

    def _get_doc_ref(self) -> AsyncDocumentReference:
        """Returns the document reference."""
        return self._get_col_ref().document(self.get_document_id())  # type: ignore


class AsyncModel(AsyncBareModel):
    __document_id__: str = "id"
    id: Optional[str] = None

    @classmethod
    async def get_by_id(cls: Type[TAsyncBareModel], id_: str) -> TAsyncBareModel:
        return await cls.get_by_doc_id(id_)


class AsyncBareSubCollection(ABC):
    __collection_tpl__: Optional[str] = None
    __document_id__: str

    @classmethod
    def model_for(cls, parent, model_class):
        parent_props = parent.dict(by_alias=True)

        name = model_class.__name__
        ic = type(name, (model_class,), {})
        ic.__collection_cls__ = cls
        ic.__collection__ = cls.__collection_tpl__.format(**parent_props)
        ic.__document_id__ = cls.__document_id__

        return ic


class AsyncBareSubModel(AsyncBareModel, ABC):
    __collection_cls__: "AsyncBareSubCollection"
    __collection__: Optional[str] = None
    __document_id__: str

    class Collection(AsyncBareSubCollection, ABC):
        pass

    @classmethod
    def _create(cls, **kwargs) -> TAsyncBareSubModel:
        return cls(  # type: ignore
            **kwargs,
        )

    @classmethod
    def _get_col_ref(cls) -> AsyncCollectionReference:
        """Returns the collection reference."""
        if cls.__collection__ is None or "{" in cls.__collection__:
            raise CollectionNotDefined(
                f"{cls.__name__} is not properly prepared. "
                f"You should use {cls.__name__}.model_for(parent)"
            )
        return _get_col_ref(cls.__collection_cls__, cls.__collection__)

    @classmethod
    def model_for(cls, parent):
        return cls.Collection.model_for(parent, cls)


class AsyncSubModel(AsyncBareSubModel):
    id: Optional[str] = None

    @classmethod
    async def get_by_id(cls: Type[TAsyncBareModel], id_: str) -> TAsyncBareModel:
        """
        Get single item by document ID
        :raises ModelNotFoundError:
        """
        return await cls.get_by_doc_id(id_)


class AsyncSubCollection(AsyncBareSubCollection, ABC):
    __document_id__ = "id"
    __model_cls__: Type[AsyncSubModel]
