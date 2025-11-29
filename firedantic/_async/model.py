from abc import ABC
from logging import getLogger
from typing import Any, Dict, Iterable, List, Optional, Tuple, Type, TypeVar, Union

import pydantic
from google.cloud.firestore_v1 import (
    AsyncCollectionReference,
    AsyncDocumentReference,
    DocumentSnapshot,
    FieldFilter,
)
from google.cloud.firestore_v1.async_query import AsyncQuery
from google.cloud.firestore_v1.async_transaction import AsyncTransaction

import firedantic.operators as op
from firedantic import async_truncate_collection
from firedantic.common import IndexDefinition, OrderDirection
from firedantic.configurations import configuration
from firedantic.exceptions import (
    CollectionNotDefined,
    InvalidDocumentID,
    ModelNotFoundError,
)

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


def get_collection_name(cls, collection_name: Optional[str]) -> str:
    """
    Return the collection name for `cls`.

    - If `collection_name` is provided, treat it as an explicit collection name
      and prefix it using the configured prefix for the class (via __db_config__).
    - Otherwise, use the class name and the configured prefix.

    :raises CollectionNotDefined: If neither a class collection nor derived name is available.
    """
    # Resolve the config name from the model class (default to "(default)")
    config_name = getattr(cls, "__db_config__", "(default)")

    # If caller provided an explicit collection string, apply prefix from config
    if collection_name:
        cfg = configuration.get_config(config_name)
        prefix = cfg.prefix or ""
        return f"{prefix}{collection_name}"
    
    if getattr(cls, "__collection__", None):
        cfg = configuration.get_config(config_name)
        return f"{cfg.prefix or ''}{cls.__collection__}"

    raise CollectionNotDefined(f"Missing collection name for {cls.__name__}")



def _get_col_ref(cls, collection_name: Optional[str] = None) -> AsyncCollectionReference:
    """
    Return an AsyncCollectionReference for the model class using the configured async client.

    :param cls: model class
    :param collection_name: optional explicit collection name override
    :raises CollectionNotDefined: when collection cannot be resolved
    """
    # Build the prefixed collection name
    col_name = get_collection_name(cls, collection_name)

    # Resolve config name from class and fetch async client
    config_name = getattr(cls, "__db_config__", "(default)")
    async_client = configuration.get_async_client(config_name)

    # Return the AsyncCollectionReference (this is a real client call)
    col_ref = async_client.collection(col_name)

    # Ensure we got the right object back
    if not hasattr(col_ref, "document"):
        raise RuntimeError(f"_get_col_ref returned unexpected object for {cls}: {type(col_ref)!r}")
    return col_ref



class AsyncBareModel(pydantic.BaseModel, ABC):
    """
    Base model class.

    Implements basic functionality for Pydantic models, such as save, delete, find etc.
    """

    __collection__: Optional[str] = None
    __document_id__: str
    __ttl_field__: Optional[str] = None
    __composite_indexes__: Optional[Iterable[IndexDefinition]] = None
    __db_config__: str = "(default)"  # override in subclasses when needed


    async def save(
        self,
        *,
        config_name: Optional[str] = None,
        exclude_unset: bool = False,
        exclude_none: bool = False,
        transaction: Optional[AsyncTransaction] = None,
    ) -> None:
        """
        Saves this model in the database.

        :param exclude_unset: Whether to exclude fields that have not been explicitly set.
        :param exclude_none: Whether to exclude fields that have a value of `None`.
        :param transaction: Optional transaction to use.
        :raise DocumentIDError: If the document ID is not valid.
        """

        # Resolve config to use (explicit -> instance -> class -> default)
        if config_name is not None:
            resolved = config_name 
        else:
            resolved = getattr(self, "__db_config__", None)
        if not resolved:
            resolved = getattr(self.__class__, "__db_config__", "(default)")

        # Build payload - model_dump?
        data = self.model_dump(
            by_alias=True, 
            exclude_unset=exclude_unset, 
            exclude_none=exclude_none
        )
        if self.__document_id__ in data:
            del data[self.__document_id__]
        
        # Get Async collection reference using configuration - what?
        col_ref = configuration.get_async_collection_ref(self.__class__, name=resolved)
        
        # Build doc ref (use provided id if set, otherwise let server generate)
        doc_id = self.get_document_id()
        if doc_id:
            doc_ref = col_ref.document(doc_id) 
        else:
            doc_ref = col_ref.document()

        # Use transaction if provided (assume it's compatible) otherwise do direct await set
        if transaction is not None:
            # Transaction.delete/set expects DocumentReference from the same client.
            transaction.set(doc_ref, data)
        else:
            await doc_ref.set(data)

        # what does this do?
        setattr(self, self.__document_id__, doc_ref.id)

    async def delete(self, transaction: Optional[AsyncTransaction] = None) -> None:
        """
        Deletes this model from the database.

        :raise DocumentIDError: If the ID is not valid.
        """
        if transaction is not None:
            transaction.delete(self._get_doc_ref())
        else:
            await self._get_doc_ref().delete()

    async def reload(self, transaction: Optional[AsyncTransaction] = None) -> None:
        """
        Reloads this model from the database.

        :param transaction: Optional transaction to use.
        :raise ModelNotFoundError: If the document ID is missing in the model.
        """
        doc_id = self.__dict__.get(self.__document_id__)
        if doc_id is None:
            raise ModelNotFoundError("Can not reload unsaved model")

        updated_model = await self.get_by_doc_id(doc_id, transaction=transaction)
        updated_model_doc_id = updated_model.__dict__[self.__document_id__]
        assert doc_id == updated_model_doc_id

        self.__dict__.update(updated_model.__dict__)

    def get_document_id(self) -> Optional[str]:
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
    async def delete_all_for_model(cls, config_name: Optional[str] = None) -> None:

         # Resolve config to use (explicit -> instance -> class -> default)
        config_name = cls.__db_config__

        client = configuration.get_async_client(config_name)
        col_name = configuration.get_collection_name(cls, config_name=config_name)
        col_ref = client.collection(col_name)

        async for doc in col_ref.stream():
            await doc.reference.delete()


    @classmethod
    async def find(  # pylint: disable=too-many-arguments
        cls: Type[TAsyncBareModel],
        filter_: Optional[Dict[str, Union[str, dict]]] = None,
        order_by: Optional[_OrderBy] = None,
        limit: Optional[int] = None,
        offset: Optional[int] = None,
        transaction: Optional[AsyncTransaction] = None,
    ) -> List[TAsyncBareModel]:
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
        query: Union[AsyncQuery, AsyncCollectionReference] = cls._get_col_ref()
        if filter_:
            for key, value in filter_.items():
                query = cls._add_filter(query, key, value)

        if order_by is not None:
            for field, direction in order_by:
                query = query.order_by(field, direction=direction)  # type: ignore
        if limit is not None:
            query = query.limit(limit)  # type: ignore
        if offset is not None:
            query = query.offset(offset)  # type: ignore

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
                (doc.id, doc.to_dict()) async for doc in query.stream(transaction=transaction)  # type: ignore
            )
            if doc_dict is not None
        ]

    @classmethod
    def _add_filter(
        cls, query: Union[AsyncQuery, AsyncCollectionReference], field: str, value: Any
    ) -> Union[AsyncQuery, AsyncCollectionReference]:
        if isinstance(value, dict):
            for f_type in value:
                if f_type not in FIND_TYPES:
                    raise ValueError(
                        f"Unsupported filter type: {f_type}. Supported types are: {', '.join(FIND_TYPES)}"
                    )
                _filter = FieldFilter(field, f_type, value[f_type])
                query: AsyncQuery = query.where(filter=_filter)  # type: ignore
            return query
        else:
            _filter = FieldFilter(field, "==", value)
            query: AsyncQuery = query.where(filter=_filter)  # type: ignore
            return query

    @classmethod
    async def find_one(
        cls: Type[TAsyncBareModel],
        filter_: Optional[Dict[str, Union[str, dict]]] = None,
        order_by: Optional[_OrderBy] = None,
        transaction: Optional[AsyncTransaction] = None,
    ) -> TAsyncBareModel:
        """
        Returns one model from the DB based on a filter.

        :param filter_: The filter criteria.
        :param order_by: List of columns and direction to order results by.
        :return: The model instance.
        :raise ModelNotFoundError: If the entry is not found.
        """
        model = await cls.find(
            filter_, limit=1, order_by=order_by, transaction=transaction
        )
        try:
            return model[0]
        except IndexError as e:
            raise ModelNotFoundError(f"No '{cls.__name__}' found") from e

    @classmethod
    async def get_by_doc_id(
        cls: Type[TAsyncBareModel],
        doc_id: str,
        transaction: Optional[AsyncTransaction] = None,
    ) -> TAsyncBareModel:
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
            await cls._get_col_ref().document(doc_id).get(transaction=transaction)
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
    async def truncate_collection(cls, batch_size: int = 128) -> int:
        """
        Removes all documents inside a collection.

        :param batch_size: Batch size for listing documents.
        :return: Number of removed documents.
        """
        return await async_truncate_collection(
            col_ref=cls._get_col_ref(),
            batch_size=batch_size,
        )

    @classmethod
    def _get_col_ref(cls, collection_name: Optional[str] = None) -> AsyncCollectionReference:
        """
        Returns the collection reference.
        """
        return _get_col_ref(cls, collection_name)

    @classmethod
    def get_collection_name(cls) -> str:
        """
        Returns the collection name.
        """
        return get_collection_name(cls, cls.__collection__)

    def _get_doc_ref(self, config_name: Optional[str] = "(default)") -> AsyncDocumentReference:
        """
        Returns the document reference.

        :raise DocumentIDError: If the ID is not valid.
        """
        return self._get_col_ref(config_name).document(self.get_document_id())  # type: ignore

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


class AsyncModel(AsyncBareModel):
    __document_id__: str = "id"
    id: Optional[str] = None

    @classmethod
    async def get_by_id(
        cls: Type[TAsyncBareModel],
        id_: str,
        transaction: Optional[AsyncTransaction] = None,
    ) -> TAsyncBareModel:
        """
        Get single model by document ID.

        :param id_: Document ID.
        :param transaction: Optional transaction to use.
        :raises ModelNotFoundError: If no model was found by given id.
        """
        return await cls.get_by_doc_id(id_, transaction=transaction)


class AsyncBareSubCollection(ABC):
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


class AsyncBareSubModel(AsyncBareModel, ABC):
    __collection_cls__: "AsyncBareSubCollection"
    __collection__: Optional[str] = None
    __document_id__: str

    class Collection(AsyncBareSubCollection, ABC):
        pass

    @classmethod
    def _create(cls: Type[TAsyncBareSubModel], **kwargs) -> TAsyncBareSubModel:
        return cls(  # type: ignore
            **kwargs,
        )

    @classmethod
    def _get_col_ref(cls, collection_name: Optional[str]) -> AsyncCollectionReference:
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


class AsyncSubModel(AsyncBareSubModel):
    id: Optional[str] = None

    @classmethod
    async def get_by_id(
        cls: Type[TAsyncBareModel],
        id_: str,
        transaction: Optional[AsyncTransaction] = None,
    ) -> TAsyncBareModel:
        """
        Get single item by document ID

        :param id_: Document ID.
        :param transaction: Optional transaction to use.
        :raises ModelNotFoundError:
        """
        return await cls.get_by_doc_id(id_, transaction=transaction)


class AsyncSubCollection(AsyncBareSubCollection, ABC):
    __document_id__ = "id"
    __model_cls__: Type[AsyncSubModel]