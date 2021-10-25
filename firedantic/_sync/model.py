from abc import ABC
from logging import getLogger
from typing import Any, Dict, List, Optional, Type, TypeVar, Union

import pydantic
from google.cloud.firestore_v1 import (
    CollectionReference,
    DocumentReference,
    DocumentSnapshot,
)
from google.cloud.firestore_v1.base_query import BaseQuery

import firedantic.operators as op
from firedantic import truncate_collection
from firedantic.configurations import CONFIGURATIONS
from firedantic.exceptions import CollectionNotDefined, ModelNotFoundError

TBareModel = TypeVar("TBareModel", bound="BareModel")
TBareSubModel = TypeVar("TBareSubModel", bound="BareSubModel")
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


def _get_col_ref(cls, name) -> CollectionReference:
    if name is None:
        raise CollectionNotDefined(f"Missing collection name for {cls.__name__}")

    collection: CollectionReference = CONFIGURATIONS["db"].collection(
        CONFIGURATIONS["prefix"] + name
    )
    return collection


class BareModel(pydantic.BaseModel, ABC):
    """Base model class.

    Implements basic functionality for Pydantic models, such as save, delete, find etc.
    """

    __collection__: Optional[str] = None
    __document_id__: str

    def save(self) -> None:
        """Saves this model in the database."""
        data = self.dict(by_alias=True)
        if self.__document_id__ in data:
            del data[self.__document_id__]

        doc_ref = self._get_doc_ref()
        doc_ref.set(data)
        setattr(self, self.__document_id__, doc_ref.id)

    def delete(self) -> None:
        """Deletes this model from the database."""
        self._get_doc_ref().delete()

    def get_document_id(self):
        """
        Get the document ID for this model instance
        """
        return getattr(self, self.__document_id__, None)

    @classmethod
    def find(cls: Type[TBareModel], filter_: Optional[dict] = None) -> List[TBareModel]:
        """Returns a list of models from the database based on a filter.

        Example: `Company.find({"company_id": "1234567-8"})`.
        Example: `Product.find({"stock": {">=": 1}})`.

        :param filter_: The filter criteria.
        :return: List of found models.
        """
        if not filter_:
            filter_ = {}

        query: Union[BaseQuery, CollectionReference] = cls._get_col_ref()

        for key, value in filter_.items():
            query = cls._add_filter(query, key, value)

        def _cls(doc_id: str, data: Dict[str, Any]) -> TBareModel:
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
            for doc_id, doc_dict in (
                (doc.id, doc.to_dict()) for doc in query.stream()  # type: ignore
            )
            if doc_dict is not None
        ]

    @classmethod
    def _add_filter(
        cls, query: Union[BaseQuery, CollectionReference], field: str, value: Any
    ) -> Union[BaseQuery, CollectionReference]:
        if type(value) is dict:
            for f_type in value:
                if f_type not in FIND_TYPES:
                    raise ValueError(
                        f"Unsupported filter type: {f_type}. Supported types are: {', '.join(FIND_TYPES)}"
                    )
                query: BaseQuery = query.where(field, f_type, value[f_type])  # type: ignore
            return query
        else:
            query: BaseQuery = query.where(field, "==", value)  # type: ignore
            return query

    @classmethod
    def find_one(cls: Type[TBareModel], filter_: Optional[dict] = None) -> TBareModel:
        """Returns one model from the DB based on a filter.

        :param filter_: The filter criteria.
        :return: The model instance.
        :raise ModelNotFoundError: If the entry is not found.
        """
        models = cls.find(filter_)
        try:
            return models[0]
        except IndexError:
            raise ModelNotFoundError(f"No '{cls.__name__}' found")

    @classmethod
    def get_by_doc_id(cls: Type[TBareModel], doc_id: str) -> TBareModel:
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

        document: DocumentSnapshot = cls._get_col_ref().document(doc_id).get()  # type: ignore
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
    def truncate_collection(cls, batch_size: int = 128) -> int:
        """Removes all documents inside a collection.

        :param batch_size: Batch size for listing documents.
        :return: Number of removed documents.
        """
        return truncate_collection(
            col_ref=cls._get_col_ref(),
            batch_size=batch_size,
        )

    @classmethod
    def _get_col_ref(cls) -> CollectionReference:
        """Returns the collection reference."""
        return _get_col_ref(cls, cls.__collection__)

    def _get_doc_ref(self) -> DocumentReference:
        """Returns the document reference."""
        return self._get_col_ref().document(self.get_document_id())  # type: ignore


class Model(BareModel):
    __document_id__: str = "id"
    id: Optional[str] = None

    @classmethod
    def get_by_id(cls: Type[TBareModel], id_: str) -> TBareModel:
        return cls.get_by_doc_id(id_)


class BareSubCollection(ABC):
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


class BareSubModel(BareModel, ABC):
    __collection_cls__: "BareSubCollection"
    __collection__: Optional[str] = None
    __document_id__: str

    class Collection(BareSubCollection, ABC):
        pass

    @classmethod
    def _create(cls, **kwargs) -> TBareSubModel:
        return cls(  # type: ignore
            **kwargs,
        )

    @classmethod
    def _get_col_ref(cls) -> CollectionReference:
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


class SubModel(BareSubModel):
    id: Optional[str] = None

    @classmethod
    def get_by_id(cls: Type[TBareModel], id_: str) -> TBareModel:
        """
        Get single item by document ID
        :raises ModelNotFoundError:
        """
        return cls.get_by_doc_id(id_)


class SubCollection(BareSubCollection, ABC):
    __document_id__ = "id"
    __model_cls__: Type[SubModel]
