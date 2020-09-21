from google.cloud import firestore

CONFIGURATIONS = {}


def configure(db: firestore.Client, prefix: str = "") -> None:
    """Configures the prefix and DB.

    :param db: The firestore client instance.
    :param prefix: The prefix to use for collection names.
    """
    global CONFIGURATIONS

    CONFIGURATIONS["db"] = db
    CONFIGURATIONS["prefix"] = prefix
