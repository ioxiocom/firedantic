# Firedantic

[![Build Status](https://travis-ci.org/digitalliving/firedantic.svg?branch=master)](https://travis-ci.org/digitalliving/firedantic)

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
from mock import Mock
from os import environ

import google.auth.credentials
from firedantic import configure
from google.cloud import firestore

# Firestore emulator must be running if using locally.
if environ.get("FIRESTORE_EMULATOR_HOST"):
    client = firestore.Client(
        project="firedantic-test",
        credentials=Mock(spec=google.auth.credentials.Credentials)
    )
else:
    client = firestore.Client()

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

## License

This code is released under the BSD 3-Clause license. Details in the
[LICENSE](./LICENSE) file.
