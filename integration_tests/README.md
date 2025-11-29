# integration_tests/README.md

## Overview
This folder contains three integration test files. This README explains how to run them and what each file is for.

## Prerequisites
- Python 3.13
- Run: 
```bash
python -m venv firedantic
source firedantic/bin/activate
cd firedantic/integration_tests
```

## Files and purpose (replace placeholders with real filenames)
- `integration_tests/configure_firestore_db_clients.py` — Purpose: shows how to create and connect to various db clients.
- `integration_tests/full_sync_flow.py` — Purpose: configures clients, saves data to db, finds the data, and deletes all data in a sync fashion.
- `integration_tests/full_async_flow.py` — Purpose: configures async clients, saves data to db, finds the data, and deletes all data in an async fashion.


## How to run
Run each individual test file:
    - `python configure_firestore_db_clients.py`
    - `python full_sync_flow.py`
    - `python full_async_flow.py`


## Environment and configuration
- Ensure firestore emulator is running in another terminal window:
    - `./start_emulator.sh`

## What to expect:
- For the configure_firestore_db_clients test, you should expect to see the following:
`All configure_firestore_db_client tests passed!`

- For the `full_sync_flow` and `full_async_flow`, you should expect to see the following output: \
You can readily play around with the models to update the data as desired.
```
Number of company owners with first name: 'Bill': 1

Number of companies with id: '1234567-7': 1

Number of company owners with first name: 'John': 1

Number of companies with id: '1234567-8a': 1

Number of company owners with first name: 'Alice': 1

Number of billing companies with id: '1234567-8c': 1

Number of billing accounts with billing_id: 801048: 1
```