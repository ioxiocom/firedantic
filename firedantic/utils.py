from typing import Iterator


def get_all_subclasses(cls) -> Iterator:
    """
    Recursively get all subclasses of a class.
    """
    for subclass in cls.__subclasses__():
        yield subclass
        yield from get_all_subclasses(subclass)


def remove_prefix(text: str, prefix: str) -> str:
    """
    Needed for Python 3.8 support.
    """
    if text.startswith(prefix):
        return text[len(prefix) :]
    else:
        return text
