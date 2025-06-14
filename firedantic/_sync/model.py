from abc import ABC
from logging import getLogger
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, TypeVar, Union

import pydantic
from google.cloud.firestore_v1 import (
    CollectionReference,
    DocumentReference,
    DocumentSnapshot,
    FieldFilter,
)
from google.cloud.firestore_v1.base_query import BaseQuery
from google.cloud.firestore_v1.transaction import Transaction

import firedantic.operators as op
from firedantic import truncate_collection
from firedantic.common import IndexDefinition, OrderDirection
from firedantic.configurations import CONFIGURATIONS
from firedantic.exceptions import (
    CollectionNotDefined,
    InvalidDocumentID,
    ModelNotFoundError,
)

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


def get_collection_name(cls, name: Optional[str]) -> str:
    """
    Returns the collection name.

    :raise CollectionNotDefined: If the collection name is not defined.
    """
    if not name:
        raise CollectionNotDefined(f"Missing collection name for {cls.__name__}")

    return f"{CONFIGURATIONS['prefix']}{name}"


def _get_col_ref(cls, name: Optional[str]) -> CollectionReference:
    collection: CollectionReference = CONFIGURATIONS["db"].collection(
        get_collection_name(cls, name)
    )
    return collection


class BareModel(pydantic.BaseModel, ABC):
    """
    Base model class.

    Implements basic functionality for Pydantic models, such as save, delete, find etc.
    """

    __collection__: Optional[str] = None
    __document_id__: str
    __ttl_field__: Optional[str] = None
    __composite_indexes__: Optional[Iterable[IndexDefinition]] = None

    def save(
        self,
        *,
        exclude_unset: bool = False,
        exclude_none: bool = False,
        transaction: Optional[Transaction] = None,
    ) -> None:
        """
        Saves this model in the database.

        :param exclude_unset: Whether to exclude fields that have not been explicitly set.
        :param exclude_none: Whether to exclude fields that have a value of `None`.
        :param transaction: Optional transaction to use.
        :raise DocumentIDError: If the document ID is not valid.
        """
        data = self.model_dump(
            by_alias=True, exclude_unset=exclude_unset, exclude_none=exclude_none
        )
        if self.__document_id__ in data:
            del data[self.__document_id__]

        doc_ref = self._get_doc_ref()
        if transaction is not None:
            transaction.set(doc_ref, data)
        else:
            doc_ref.set(data)
        setattr(self, self.__document_id__, doc_ref.id)

    def delete(self, transaction: Optional[Transaction] = None) -> None:
        """
        Deletes this model from the database.

        :raise DocumentIDError: If the ID is not valid.
        """
        if transaction is not None:
            transaction.delete(self._get_doc_ref())
        else:
            self._get_doc_ref().delete()

    def reload(self, transaction: Optional[Transaction] = None) -> None:
        """
        Reloads this model from the database.

        :param transaction: Optional transaction to use.
        :raise ModelNotFoundError: If the document ID is missing in the model.
        """
        doc_id = self.__dict__.get(self.__document_id__)
        if doc_id is None:
            raise ModelNotFoundError("Can not reload unsaved model")

        updated_model = self.get_by_doc_id(doc_id, transaction=transaction)
        updated_model_doc_id = updated_model.__dict__[self.__document_id__]
        assert doc_id == updated_model_doc_id

        self.__dict__.update(updated_model.__dict__)

    def get_document_id(self):
        """
        Returns the document ID for this model instance.

        :raise DocumentIDError: If the ID is not valid.
        """
        doc_id = getattr(self, self.__document_id__, None)
        if doc_id is not None:
            self._validate_document_id(doc_id)
        return getattr(self, self.__document_id__, None)

    _OrderBy = List[Tuple[str, OrderDirection]]

    @classmethod
    def find(  # pylint: disable=too-many-arguments
        cls: Type[TBareModel],
        filter_: Optional[Dict[str, Union[str, dict]]] = None,
        order_by: Optional[_OrderBy] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        transaction: Optional[Transaction] = None,
    ) -> List[TBareModel]:
        """
        Returns a list of models from the database based on a filter.

        The list can be sorted with the order_by parameter, limits and offets can also be applied.

        Example: `Company.find({"company_id": "1234567-8"})`.
        Example: `Product.find({"stock": {">=": 1}})`.
        Example: `Product.find(order_by=[('unit_value', Query.ASCENDING), ('stock', Query.DESCENDING)], limit=2)`.
        Example: `Product.find({"stock": {">=": 3}}, order_by=[('unit_value', Query.ASCENDING)], limit=2, offset=3)`.

        :param filter_: The filter criteria.
        :param order_by: List of columns and direction to order results by.
        :param limit: Maximum results to return.
        :param offset: Skip the first n results.
        :param transaction: Optional transaction to use.
        :return: List of found models.
        """
        query: Union[BaseQuery, CollectionReference] = cls._get_col_ref()
        if filter_:
            for key, value in filter_.items():
                query = cls._add_filter(query, key, value)

        if order_by is not None:
            for order_by_item in order_by:
                field, direction = order_by_item
                query = query.order_by(field, direction=direction)  # type: ignore
        if limit is not None:
            query = query.limit(limit)  # type: ignore
        if offset is not None:
            query = query.offset(offset)  # type: ignore

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
                (doc.id, doc.to_dict()) for doc in query.stream(transaction=transaction)  # type: ignore
            )
            if doc_dict is not None
        ]

    @classmethod
    def _add_filter(
        cls, query: Union[BaseQuery, CollectionReference], field: str, value: Any
    ) -> Union[BaseQuery, CollectionReference]:
        if isinstance(value, dict):
            for f_type in value:
                if f_type not in FIND_TYPES:
                    raise ValueError(
                        f"Unsupported filter type: {f_type}. Supported types are: {', '.join(FIND_TYPES)}"
                    )
                _filter = FieldFilter(field, f_type, value[f_type])
                query: BaseQuery = query.where(filter=_filter)  # type: ignore
            return query
        else:
            _filter = FieldFilter(field, "==", value)
            query: BaseQuery = query.where(filter=_filter)  # type: ignore
            return query

    @classmethod
    def find_one(
        cls: Type[TBareModel],
        filter_: Optional[Dict[str, Union[str, dict]]] = None,
        order_by: Optional[_OrderBy] = None,
        transaction: Optional[Transaction] = None,
    ) -> TBareModel:
        """
        Returns one model from the DB based on a filter.

        :param filter_: The filter criteria.
        :param order_by: List of columns and direction to order results by.
        :return: The model instance.
        :raise ModelNotFoundError: If the entry is not found.
        """
        model = cls.find(filter_, limit=1, order_by=order_by, transaction=transaction)
        try:
            return model[0]
        except IndexError as e:
            raise ModelNotFoundError(f"No '{cls.__name__}' found") from e

    @classmethod
    def get_by_doc_id(
        cls: Type[TBareModel],
        doc_id: str,
        transaction: Optional[Transaction] = None,
    ) -> TBareModel:
        """
        Returns a model based on the document ID.

        :param doc_id: The document ID of the entry.
        :param transaction: Optional transaction to use.
        :return: The model.
        :raise ModelNotFoundError: Raised if no matching document is found.
        """

        try:
            cls._validate_document_id(doc_id)
        except InvalidDocumentID as e:
            # Getting a document with doc_id set to an empty string would raise a
            # google.api_core.exceptions.InvalidArgument exception and a doc_id
            # containing an uneven number of slashes would raise a
            # ValueError("A document must have an even number of path elements") and
            # could even load data from a sub collection instead of the desired one.
            raise ModelNotFoundError(
                f"No '{cls.__name__}' found with {cls.__document_id__} '{doc_id}'"
            ) from e

        document: DocumentSnapshot = (
            cls._get_col_ref().document(doc_id).get(transaction=transaction)
        )  # type: ignore
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
        """
        Removes all documents inside a collection.

        :param batch_size: Batch size for listing documents.
        :return: Number of removed documents.
        """
        return truncate_collection(
            col_ref=cls._get_col_ref(),
            batch_size=batch_size,
        )

    @classmethod
    def _get_col_ref(cls) -> CollectionReference:
        """
        Returns the collection reference.
        """
        return _get_col_ref(cls, cls.__collection__)

    @classmethod
    def get_collection_name(cls) -> str:
        """
        Returns the collection name.
        """
        return get_collection_name(cls, cls.__collection__)

    def _get_doc_ref(self) -> DocumentReference:
        """
        Returns the document reference.

        :raise DocumentIDError: If the ID is not valid.
        """
        return self._get_col_ref().document(self.get_document_id())  # type: ignore

    @staticmethod
    def _validate_document_id(document_id: str):
        """
        Validates the Document ID is valid.

        Based on information from https://firebase.google.com/docs/firestore/quotas#limits

        :raise DocumentIDError: If the ID is not valid.
        """
        if len(document_id.encode("utf-8")) > 1500:
            raise InvalidDocumentID("Document ID must be no longer than 1,500 bytes")

        if "/" in document_id:
            raise InvalidDocumentID("Document ID cannot contain a forward slash (/)")

        if (
            document_id.startswith("__")
            and document_id.endswith("__")
            and len(document_id) >= 4
        ):
            raise InvalidDocumentID(
                "Document ID cannot match the regular expression __.*__"
            )

        if document_id in (".", ".."):
            raise InvalidDocumentID(
                "Document ID cannot solely consist of a single period (.) or double "
                "periods (..)"
            )

        if document_id == "":
            raise InvalidDocumentID("Document ID cannot be an empty string")


class Model(BareModel):
    __document_id__: str = "id"
    id: Optional[str] = None

    @classmethod
    def get_by_id(
        cls: Type[TBareModel],
        id_: str,
        transaction: Optional[Transaction] = None,
    ) -> TBareModel:
        """
        Get single model by document ID.

        :param id_: Document ID.
        :param transaction: Optional transaction to use.
        :raises ModelNotFoundError: If no model was found by given id.
        """
        return cls.get_by_doc_id(id_, transaction=transaction)


class BareSubCollection(ABC):
    __collection_tpl__: Optional[str] = None
    __document_id__: str

    @classmethod
    def model_for(cls, parent, model_class):
        """
        Returns the model for this subcollection.
        """
        parent_props = parent.model_dump(by_alias=True)

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
    def _create(cls: Type[TBareSubModel], **kwargs) -> TBareSubModel:
        return cls(  # type: ignore
            **kwargs,
        )

    @classmethod
    def _get_col_ref(cls) -> CollectionReference:
        """
        Returns the collection reference.
        """
        if cls.__collection__ is None or "{" in cls.__collection__:
            raise CollectionNotDefined(
                f"{cls.__name__} is not properly prepared. "
                f"You should use {cls.__name__}.model_for(parent)"
            )
        return _get_col_ref(cls.__collection_cls__, cls.__collection__)

    @classmethod
    def model_for(cls, parent):
        """
        Returns the model for this submodel.
        """
        return cls.Collection.model_for(parent, cls)


class SubModel(BareSubModel):
    id: Optional[str] = None

    @classmethod
    def get_by_id(
        cls: Type[TBareModel],
        id_: str,
        transaction: Optional[Transaction] = None,
    ) -> TBareModel:
        """
        Get single item by document ID

        :param id_: Document ID.
        :param transaction: Optional transaction to use.
        :raises ModelNotFoundError:
        """
        return cls.get_by_doc_id(id_, transaction=transaction)


class SubCollection(BareSubCollection, ABC):
    __document_id__ = "id"
    __model_cls__: Type[SubModel]
