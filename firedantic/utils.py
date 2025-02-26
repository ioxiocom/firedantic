from typing import Iterator


def get_all_subclasses(cls) -> Iterator:
    """
    Recursively get all subclasses of a class.
    """
    for subclass in cls.__subclasses__():
        yield subclass
        yield from get_all_subclasses(subclass)
