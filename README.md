# Firedantic

[![GitHub Workflow Status](https://img.shields.io/github/actions/workflow/status/ioxiocom/firedantic/publish.yaml)](https://github.com/ioxiocom/firedantic/actions/workflows/publish.yaml)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![PyPI](https://img.shields.io/pypi/v/firedantic)](https://pypi.org/project/firedantic/)
[![PyPI - Python Version](https://img.shields.io/pypi/pyversions/firedantic)](https://pypi.org/project/firedantic/)
[![License: BSD 3-Clause](https://img.shields.io/badge/License-BSD%203--Clause-blue.svg)](https://opensource.org/licenses/BSD-3-Clause)

Database models for Firestore using Pydantic base models.

## Installation

The package is available on PyPI:

```bash
pip install firedantic
```

## Usage

In your application you will need to configure the firestore db client and optionally
the collection prefix, which by default is empty.

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

# Reloads model data from the database
company.reload()
```

Querying is done via a MongoDB-like `find()`:

```python
from firedantic import Model
import firedantic.operators as op
from google.cloud.firestore import Query

class Product(Model):
    __collection__ = "products"
    product_id: str
    stock: int
    unit_value: int


Product.find({"product_id": "abc-123"})
Product.find({"stock": {">=": 3}})
# or
Product.find({"stock": {op.GTE: 3}})
Product.find({"stock": {">=": 1}}, order_by=[('unit_value', Query.ASCENDING)], limit=25, offset=50)
Product.find(order_by=[('unit_value', Query.ASCENDING), ('stock', Query.DESCENDING)], limit=2)
```

The query operators are found at
[https://firebase.google.com/docs/firestore/query-data/queries#query_operators](https://firebase.google.com/docs/firestore/query-data/queries#query_operators).

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
    asyncio.run(main())
```

## Subcollections

Subcollections in Firestore are basically dynamically named collections.

Firedantic supports them via the `SubCollection` and `SubModel` classes, by creating
dynamic classes with collection name determined based on the "parent" class it is in
reference to using the `model_for()` method.

```python
from typing import Optional, Type

from firedantic import AsyncModel, AsyncSubCollection, AsyncSubModel, ModelNotFoundError


class UserStats(AsyncSubModel):
    id: Optional[str] = None
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

## Composite Indexes and TTL Policies

Firedantic has support for defining composite indexes and TTL policies as well as
creating them.

### Composite indexes

Composite indexes of a collection are defined in `__composite_indexes__`, which is a
list of all indexes to be created.

To define an index, you can use `collection_index` or `collection_group_index`,
depending on the query scope of the index. Each of these takes in an arbitrary amount of
tuples, where the first element is the field name and the second is the order
(`ASCENDING`/`DESCENDING`).

The `set_up_composite_indexes` and `async_set_up_composite_indexes` functions are used
to create indexes.

For more details, see the example further down.

### TTL Policies

The field used for the TTL policy should be a datetime field and the name of the field
should be defined in `__ttl_field__`. The `set_up_ttl_policies` and
`async_set_up_ttl_policies` functions are used to set up the policies.

Note: The TTL policies can not be set up in the Firestore emulator.

### Examples

Below are examples (both sync and async) to show how to use Firedantic to set up
composite indexes and TTL policies.

The examples use `async_set_up_composite_indexes_and_ttl_policies` and
`set_up_composite_indexes_and_ttl_policies` functions to set up both composite indexes
and TTL policies. However, you can use separate functions to set up only either one of
them.

#### Composite Index and TTL Policy Example (sync)

```python
from datetime import datetime

from firedantic import (
    collection_index,
    collection_group_index,
    configure,
    get_all_subclasses,
    Model,
    set_up_composite_indexes_and_ttl_policies,
)
from google.cloud.firestore import Client, Query
from google.cloud.firestore_admin_v1 import FirestoreAdminClient


class ExpiringModel(Model):
    __collection__ = "expiringModel"
    __ttl_field__ = "expire"
    __composite_indexes__ = [
        collection_index(("content", Query.ASCENDING), ("expire", Query.DESCENDING)),
        collection_group_index(("content", Query.DESCENDING), ("expire", Query.ASCENDING)),
    ]

    expire: datetime
    content: str


def main():
    configure(Client(), prefix="firedantic-test-")
    set_up_composite_indexes_and_ttl_policies(
        gcloud_project="my-project",
        models=get_all_subclasses(Model),
        client=FirestoreAdminClient(),
    )
    # or use set_up_composite_indexes / set_up_ttl_policies functions separately


if __name__ == "__main__":
    main()
```

#### Composite Index and TTL Policy Example (async)

```python
import asyncio
from datetime import datetime

from firedantic import (
    AsyncModel,
    async_set_up_composite_indexes_and_ttl_policies,
    collection_index,
    collection_group_index,
    configure,
    get_all_subclasses,
)
from google.cloud.firestore import AsyncClient, Query
from google.cloud.firestore_admin_v1.services.firestore_admin import (
    FirestoreAdminAsyncClient,
)


class ExpiringModel(AsyncModel):
    __collection__ = "expiringModel"
    __ttl_field__ = "expire"
    __composite_indexes__ = [
        collection_index(("content", Query.ASCENDING), ("expire", Query.DESCENDING)),
        collection_group_index(("content", Query.DESCENDING), ("expire", Query.ASCENDING)),
    ]

    expire: datetime
    content: str


async def main():
    configure(AsyncClient(), prefix="firedantic-test-")
    await async_set_up_composite_indexes_and_ttl_policies(
        gcloud_project="my-project",
        models=get_all_subclasses(AsyncModel),
        client=FirestoreAdminAsyncClient(),
    )
    # or await async_set_up_composite_indexes / async_set_up_ttl_policies separately


if __name__ == "__main__":
    asyncio.run(main())
```

## Transactions

Firedantic has basic support for
[Firestore Transactions](https://firebase.google.com/docs/firestore/manage-data/transactions).
The following methods can be used in a transaction:

- `Model.delete(transaction=transaction)`
- `Model.find_one(transaction=transaction)`
- `Model.find(transaction=transaction)`
- `Model.get_by_doc_id(transaction=transaction)`
- `Model.get_by_id(transaction=transaction)`
- `Model.reload(transaction=transaction)`
- `Model.save(transaction=transaction)`
- `SubModel.get_by_id(transaction=transaction)`

When using transactions, note that read operations must come before write operations.

### Transaction examples

In this example (async and sync version of it below), we are updating a `City` to
increment and decrement the population of it, both using an instance method and a
standalone function. Please note that the `@async_transactional` and `@transactional`
decorators always expect the first argument of the wrapped function to be `transaction`;
i.e. you can not directly wrap an instance method that has `self` as the first argument
or a class method that has `cls` as the first argument.

#### Transaction example (async)

```python
import asyncio
from os import environ
from unittest.mock import Mock

import google.auth.credentials
from google.cloud.firestore import AsyncClient
from google.cloud.firestore_v1 import async_transactional, AsyncTransaction

from firedantic import AsyncModel, configure, get_async_transaction

# Firestore emulator must be running if using locally.
if environ.get("FIRESTORE_EMULATOR_HOST"):
    client = AsyncClient(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )
else:
    client = AsyncClient()

configure(client, prefix="firedantic-test-")


class City(AsyncModel):
    __collection__ = "cities"
    population: int

    async def increment_population(self, increment: int = 1):
        @async_transactional
        async def _increment_population(transaction: AsyncTransaction) -> None:
            await self.reload(transaction=transaction)
            self.population += increment
            await self.save(transaction=transaction)

        t = get_async_transaction()
        await _increment_population(transaction=t)


async def main():
    @async_transactional
    async def decrement_population(
        transaction: AsyncTransaction, city: City, decrement: int = 1
    ):
        await city.reload(transaction=transaction)
        city.population = max(0, city.population - decrement)
        await city.save(transaction=transaction)

    c = City(id="SF", population=1)
    await c.save()
    await c.increment_population(increment=1)
    assert c.population == 2

    t = get_async_transaction()
    await decrement_population(transaction=t, city=c, decrement=5)
    assert c.population == 0


if __name__ == "__main__":
    asyncio.run(main())
```

#### Transaction example (sync)

```python
from os import environ
from unittest.mock import Mock

import google.auth.credentials
from google.cloud.firestore import Client
from google.cloud.firestore_v1 import transactional, Transaction

from firedantic import Model, configure, get_transaction

# Firestore emulator must be running if using locally.
if environ.get("FIRESTORE_EMULATOR_HOST"):
    client = Client(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials),
    )
else:
    client = Client()

configure(client, prefix="firedantic-test-")


class City(Model):
    __collection__ = "cities"
    population: int

    def increment_population(self, increment: int = 1):
        @transactional
        def _increment_population(transaction: Transaction) -> None:
            self.reload(transaction=transaction)
            self.population += increment
            self.save(transaction=transaction)

        t = get_transaction()
        _increment_population(transaction=t)


def main():
    @transactional
    def decrement_population(
        transaction: Transaction, city: City, decrement: int = 1
    ):
        city.reload(transaction=transaction)
        city.population = max(0, city.population - decrement)
        city.save(transaction=transaction)

    c = City(id="SF", population=1)
    c.save()
    c.increment_population(increment=1)
    assert c.population == 2

    t = get_transaction()
    decrement_population(transaction=t, city=c, decrement=5)
    assert c.population == 0


if __name__ == "__main__":
    main()
```

## Development

PRs are welcome!

### Prequisites:

- [pipx](https://pipx.pypa.io/stable/installation/) (to install poetry, if needed)
- `pipx install poetry`
- `pip install pre-commit`
- [nvm](https://github.com/nvm-sh/nvm)
- `npm` (for firebase CLI installation)
- [java](http://www.java.com) via `brew install openjdk@21`

### Running Firestore emulator

To run the Firestore emulator locally you will need:

- [Firebase CLI](https://firebase.google.com/docs/cli)

To install the `firebase` CLI run:

```bash
npm install -g firebase-tools
```

Run the Firestore emulator with a predictable port:

```bash
./start_emulator.sh
# or on Windows run the .bat file
start_emulator
```

### Tests

To run tests locally, you should first:

Set the host:

```bash
export FIRESTORE_EMULATOR_HOST=<host port>
```

Then run poetry:

```bash
poetry install
poetry run invoke test
```

\*Note, the emulator must be set and running for all tests to pass.

### About sync and async versions of library

Although this library provides both sync and async versions of models, please keep in
mind that you need to explicitly maintain only async version of it. The synchronous
version is generated automatically by invoke task:

```bash
poetry run invoke unasync
```

We decided to go this way in order to:

- make sure both versions have the same API
- reduce human error factor
- avoid working on two code bases at the same time to reduce maintenance effort

Thus, please make sure you don't modify any of files under
[firedantic/\_sync](./firedantic/_sync) and
[firedantic/tests/tests_sync](./firedantic/tests/tests_sync) by hands. `unasync` is also
running as part of pre-commit hooks, but in order to run the latest version of tests you
have to run it manually.

### Generating changelog

After you have increased the version number in [pyproject.toml](pyproject.toml), please
run the following command to generate a changelog placeholder and fill in the relevant
information about the release in [CHANGELOG.md](CHANGELOG.md):

```bash
poetry run invoke make-changelog
```

## License

This code is released under the BSD 3-Clause license. Details in the
[LICENSE](./LICENSE) file.
