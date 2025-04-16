from google.cloud.firestore_v1 import AsyncCollectionReference


async def truncate_collection(
    col_ref: AsyncCollectionReference, batch_size: int = 128
) -> int:
    """
    Removes all documents inside a collection.

    :param col_ref: A collection reference to the collection to be truncated.
    :param batch_size: Batch size for listing documents.
    :return: Number of removed documents.
    """
    count = 0

    while True:
        deleted = 0
        async for doc in col_ref.limit(batch_size).stream():  # type: ignore
            await doc.reference.delete()
            deleted += 1

        count += deleted
        if deleted < batch_size:
            return count
