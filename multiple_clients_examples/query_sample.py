from company_models import Company
from configure_firestore_db_client import configure_client, configure_multiple_clients

import firedantic.operators as op

# Firestore emulator must be running if using locally.
# Supported types are: <, >, array_contains, in, ==, !=, not-in, <=, array_contains_any, >=


print("\n---- Running OLD way ----")
configure_client()

companies1 = Company.find({"owner.first_name": "John"})
companies2 = Company.find({"owner.first_name": {op.EQ: "John"}})
companies3 = Company.find({"owner.first_name": {"==": "John"}})
print(companies1)

assert companies1 != []
assert companies1 == companies2 == companies3


print("\n---- Running NEW way ----")
configure_multiple_clients()

companies1 = Company.find({"owner.first_name": "Alice"})
companies2 = Company.find({"owner.first_name": {op.EQ: "Alice"}})
companies3 = Company.find({"owner.first_name": {"==": "Alice"}})
print(companies1)
assert companies1 != []
assert companies1 == companies2 == companies3
