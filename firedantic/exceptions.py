"""Firedantic Exceptions module."""


class ConfigurationNotFoundError(Exception):
    """Raised when a configuration is not found."""


class ModelError(Exception):
    """Generic model error class."""


class InvalidDocumentID(ModelError):
    """Raised when a document ID is invalid."""


class ModelNotFoundError(ModelError):
    """Raised when a model is not found."""


class CollectionNotDefined(ModelError):
    """Raised when the model collection is not defined."""
