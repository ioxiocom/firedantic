# Firedantic

[![Build Status](https://travis-ci.com/digitalliving/firedantic.svg?branch=master)](https://travis-ci.com/digitalliving/firedantic)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI](https://img.shields.io/pypi/v/firedantic)](https://pypi.org/project/firedantic/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firedantic)](https://pypi.org/project/firedantic/)
[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

Database models for Firestore using Pydantic base models.


## Installation

The package is available on PyPi:

```bash
pip install firedantic
```


## Usage

In your application you will need to configure the firestore db client and
optionally the collection prefix, which by default is empty.

```python
from os import environ
from unittest.mock import Mock

import google.auth.credentials
from firedantic import configure
from google.cloud.firestore import Client

# Firestore emulator must be running if using locally.
if environ.get("FIRESTORE_EMULATOR_HOST"):
    client = Client(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials)
    )
else:
    client = Client()

configure(client, prefix="firedantic-test-")
```

Once that is done, you can start defining your Pydantic models, e.g:

```python
from pydantic import BaseModel

from firedantic import Model

class Owner(BaseModel):
    """Dummy owner Pydantic model."""
    first_name: str
    last_name: str


class Company(Model):
    """Dummy company Firedantic model."""
    __collection__ = "companies"
    company_id: str
    owner: Owner

# Now you can use the model to save it to Firestore
owner = Owner(first_name="John", last_name="Doe")
company = Company(company_id="1234567-8", owner=owner)
company.save()

# Prints out the firestore ID of the Company model
print(company.id)
```

Querying is done via a MongoDB-like `find()`:

```python
from firedantic import Model
import firedantic.operators as op

class Product(Model):
    __collection__ = "products"
    product_id: str
    stock: int


Product.find({"product_id": "abc-123"})
Product.find({"stock": {">=": 3}})
# or
Product.find({"stock": {op.GTE: 3}})
```

The query operators are found at [https://firebase.google.com/docs/firestore/query-data/queries#query_operators](https://firebase.google.com/docs/firestore/query-data/queries#query_operators).


### Async usage

Firedantic can also be used in an async way, like this:
```python
import asyncio
from os import environ
from unittest.mock import Mock

import google.auth.credentials
from google.cloud.firestore import AsyncClient

from firedantic import AsyncModel, configure

# Firestore emulator must be running if using locally.
if environ.get("FIRESTORE_EMULATOR_HOST"):
    client = AsyncClient(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )
else:
    client = AsyncClient()

configure(client, prefix="firedantic-test-")


class Person(AsyncModel):
    __collection__ = "persons"
    name: str


async def main():
    alice = Person(name="Alice")
    await alice.save()
    print(f"Saved Alice as {alice.id}")
    bob = Person(name="Bob")
    await bob.save()
    print(f"Saved Bob as {bob.id}")

    found_alice = await Person.find_one({"name": "Alice"})
    print(f"Found Alice: {found_alice.id}")
    assert alice.id == found_alice.id

    found_bob = await Person.get_by_id(bob.id)
    assert bob.id == found_bob.id
    print(f"Found Bob: {found_bob.id}")

    await alice.delete()
    print("Deleted Alice")
    await bob.delete()
    print("Deleted Bob")


if __name__ == "__main__":
    # Starting from Python 3.7 ->
    # asyncio.run(main())

    # Compatible with Python 3.6 ->
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(main())
```

## Subcollections

Subcollections in Firestore are basically dynamically named collections.

Firedantic supports them via the `SubCollection` and `SubModel` classes, by creating dynamic classes with collection name determined based on the "parent" class it is in reference to using the `model_for()` method.

```python
from typing import Optional, Type

from firedantic import AsyncModel, AsyncSubCollection, AsyncSubModel, ModelNotFoundError


class UserStats(AsyncSubModel):
    id: Optional[str]
    purchases: int = 0

    class Collection(AsyncSubCollection):
        # Can use any properties of the "parent" model
        __collection_tpl__ = "users/{id}/stats"


class User(AsyncModel):
    __collection__ = "users"
    name: str


async def get_user_purchases(user_id: str, period: str = "2021") -> int:
    user = await User.get_by_id(user_id)
    stats_model: Type[UserStats] = UserStats.model_for(user)
    try:
        stats = await stats_model.get_by_id(period)
    except ModelNotFoundError:
        stats = stats_model()
    return stats.purchases

```

## Development

PRs are welcome!



To run tests locally, you should run:

```bash
poetry install
poetry run invoke test
```

### About sync and async versions of library

Although this library provides both sync and async versions of models, please keep in mind that
you need to explicitly maintain only async version of it. The synchronous version is generated automatically by invoke task:

```bash
poetry run invoke unasync
```

We decided to go this way in order to:
- make sure both versions have the same API
- reduce human error factor
- avoid working on two code bases at the same time to reduce maintenance effort

Thus, please make sure you don't modify any of files under [firedantic/_sync](./firedantic/_sync) and [firedantic/tests/tests_sync](./firedantic/tests/tests_sync) by hands.
`unasync` is also running as part of pre-commit hooks, but in order to run the latest version of tests you have to run it manually.

## License

This code is released under the BSD 3-Clause license. Details in the
[LICENSE](./LICENSE) file.
