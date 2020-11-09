from abc import ABC
from typing import List, Optional, Type, TypeVar

import pydantic
from google.cloud.firestore_v1 import CollectionReference, DocumentReference

from firedantic.configurations import CONFIGURATIONS
from firedantic.exceptions import CollectionNotDefined, ModelNotFoundError

TModel = TypeVar("TModel", bound="Model")


class Model(pydantic.BaseModel, ABC):
    """Base model class.

    Implements basic functionality for Pydantic models, such as save, delete, find etc.
    """

    __collection__: Optional[str] = None

    id: Optional[str] = None

    def save(self) -> None:
        """Saves this model in the database."""
        data = self.dict(by_alias=True)
        if "id" in data:
            del data["id"]

        doc_ref = self._get_doc_ref()
        doc_ref.set(data)
        self.id = doc_ref.id

    def delete(self) -> None:
        """Deletes this model from the database."""
        self._get_doc_ref().delete()

    @classmethod
    def find(cls: Type[TModel], filter_: dict) -> List[TModel]:
        """Returns a list of models from the database based on a filter.

        Example: `Company.find({"company_id": "1234567-8"})`.
        Currently only supports `==` operator.

        :param filter_: The filter criteria.
        :return: List of found models.
        """
        coll = cls._get_col_ref()

        query = coll

        for key, value in filter_.items():
            query = query.where(key, "==", value)

        return [cls(id=doc.id, **doc.to_dict()) for doc in query.stream()]

    @classmethod
    def find_one(cls: Type[TModel], filter_: dict) -> TModel:
        """Returns one model from the DB based on a filter.

        :param filter_: The filter criteria.
        :return: The model instance.
        :raise ModelNotFoundError: If the entry is not found.
        """
        try:
            return cls.find(filter_)[0]
        except IndexError:
            raise ModelNotFoundError(f"No '{cls.__name__}' found")

    @classmethod
    def get_by_id(cls: Type[TModel], id_: str) -> TModel:
        """Returns a model based on the ID.

        :param id_: The id of the entry.
        :return: The model.
        :raise ModelNotFoundError: Raised if no matching document is found.
        """
        document = cls._get_col_ref().document(id_).get()
        if not document.exists:
            raise ModelNotFoundError(f"No '{cls.__name__}' found with id '{id_}'")
        data = document.to_dict()
        data["id"] = id_
        return cls(**data)

    @classmethod
    def truncate_collection(cls) -> int:
        """Removes all documents inside a collection.

        :return: Number of removed documents.
        """
        removed = 0
        for doc_ref in cls._get_col_ref().list_documents():
            doc_ref.delete()
            removed += 1
        return removed

    @classmethod
    def _get_col_ref(cls) -> CollectionReference:
        """Returns the collection reference."""
        if cls.__collection__ is None:
            raise CollectionNotDefined(f"Missing collection name for {cls.__name__}")
        return CONFIGURATIONS["db"].collection(
            CONFIGURATIONS["prefix"] + cls.__collection__
        )

    def _get_doc_ref(self) -> DocumentReference:
        """Returns the document reference."""
        return self._get_col_ref().document(self.id)
