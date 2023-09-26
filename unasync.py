# Modification of https://github.com/encode/httpcore/blob/master/unasync.py
# Original idea is taken from https://github.com/python-trio/unasync

import re
from pathlib import Path

SUBS = [
    ("google.cloud.firestore_v1.async_query", "google.cloud.firestore_v1.base_query"),
    ("AsyncQuery", "BaseQuery"),
    ("AsyncCollectionReference", "CollectionReference"),
    ("AsyncDocumentReference", "DocumentReference"),
    ("AsyncModel", "Model"),
    ("AsyncClient", "Client"),
    ("TAsyncBareModel", "TBareModel"),
    ("TAsyncBareSubModel", "TBareSubModel"),
    ("tests_async", "tests_sync"),
    ("Async([A-Z][A-Za-z0-9_]*)", r"\2"),
    ("async def", "def"),
    ("async for", "for"),
    ("async with", "with"),
    ("async_truncate_collection", "truncate_collection"),
    ("await ", ""),
    ("__aenter__", "__enter__"),
    ("__aexit__", "__exit__"),
    ("__aiter__", "__iter__"),
    ("@pytest.mark.asyncio", ""),
    ("firedantic._async.model", "firedantic._sync.model"),
    ("FirestoreAdminAsyncClient", "FirestoreAdminClient"),
]
COMPILED_SUBS = [
    (re.compile(r"(^|\b)" + regex + r"($|\b)"), repl) for regex, repl in SUBS
]


def unasync_line(line):
    for regex, repl in COMPILED_SUBS:
        line = re.sub(regex, repl, line)
    return line


def unasync_file(in_path: Path, out_path: Path):
    print(f"{in_path} -> {out_path}")
    with in_path.open("r") as in_file:
        with out_path.open("w", newline="") as out_file:
            for line in in_file.readlines():
                line = unasync_line(line)
                out_file.write(line)


def unasync_dir(in_dir: Path, out_dir: Path):
    for in_path in in_dir.glob("**/*.py"):
        out_path = out_dir / in_path.relative_to(in_dir)
        unasync_file(in_path, out_path)


def main():
    src = Path("firedantic")
    unasync_dir(src / "_async", src / "_sync")
    unasync_dir(src / "tests" / "tests_async", src / "tests" / "tests_sync")


if __name__ == "__main__":
    main()
