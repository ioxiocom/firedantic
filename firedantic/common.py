from typing import Literal, NamedTuple, Tuple, Union

OrderDirection = Union[Literal["ASCENDING"], Literal["DESCENDING"]]

IndexField = NamedTuple("IndexField", [("name", str), ("order", OrderDirection)])

IndexDefinition = NamedTuple(
    "IndexDefinition", [("query_scope", str), ("fields", Tuple[IndexField, ...])]
)


def collection_index(*fields: IndexField) -> IndexDefinition:
    """
    Shorter way to create an index definition with collection query scope

    :param fields: Index fields, each element is a tuple of name and order
    :return: IndexDefinition tuple
    """
    return IndexDefinition(query_scope="COLLECTION", fields=fields)


def collection_group_index(*fields: IndexField) -> IndexDefinition:
    """
    Shorter way to create an index definition with collection group query scope

    :param fields: Index fields, each element is a tuple of name and order
    :return: IndexDefinition tuple
    """
    return IndexDefinition(query_scope="COLLECTION_GROUP", fields=fields)
