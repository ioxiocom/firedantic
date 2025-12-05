#!/usr/bin/env python3
"""
integration_test_readme_full.py

Integration-style test script covering README examples:
- new Configuration API and legacy configure()
- sync & async model operations: save / reload / find / delete
- transactions (sync & async)
- subcollections
- multiple named configurations / per-model __db_config__
- composite indexes + TTL policies (attempted, skipped if admin client not available)

Run with a running Firestore emulator:
export FIRESTORE_EMULATOR_HOST="127.0.0.1:8686"
python test_integration_all.py
"""
from __future__ import annotations

import asyncio
import os
import sys
import time
from datetime import datetime, timedelta
from typing import Optional
from unittest.mock import Mock

import google.auth.credentials

# require firedantic package (adjust path or install locally)
try:
    # recommended imports
    from firedantic.common import IndexField
    from firedantic.configurations import configuration, CONFIGURATIONS, configure
    from firedantic import (
        Model,
        AsyncModel,
        collection_index,
        collection_group_index,
        ## IndexField,
        set_up_composite_indexes_and_ttl_policies,
        async_set_up_composite_indexes_and_ttl_policies,
        get_all_subclasses,
        get_transaction,
        get_async_transaction,
    )
    from google.cloud.firestore import Client, Query
    # from google.cloud.firestore import AsyncClient as AsyncClientSyncName  # alias to avoid name clash
    from google.cloud.firestore_v1 import AsyncClient, transactional, Transaction, async_transactional
    from google.cloud.firestore_admin_v1.services.firestore_admin import FirestoreAdminClient
    from google.cloud.firestore_admin_v1.services.firestore_admin import FirestoreAdminAsyncClient

except Exception as e:
    print("Failed to import required modules. Ensure `firedantic` is importable and google-cloud-* libs are installed.")
    raise


EMULATOR = os.environ.get("FIRESTORE_EMULATOR_HOST")
USE_EMULATOR = bool(EMULATOR)

def must(msg: str):
    print("ERROR:", msg)
    sys.exit(2)

def info(msg: str):
    print(msg)

# -----------------------
# Helpers
# -----------------------
def assert_or_exit(cond: bool, message: str):
    if not cond:
        print("ASSERTION FAILED:", message)
        raise AssertionError(message)

def cleanup_sync_collection_by_model(model_cls: type[Model]) -> None:
    """Delete everything from a model's collection (sync)."""
    info(f"Cleaning collection for sync model {model_cls.__name__}")
    # find all docs and delete
    for obj in model_cls.find({}):
        obj.delete()

async def cleanup_async_collection_by_model(model_cls: type[AsyncModel]) -> None:
    info(f"Cleaning collection for async model {model_cls.__name__}")
    items = await model_cls.find({})
    for it in items:
        await it.delete()

# admin helpers
def get_admin_client_if_possible():
    """Return admin client or None (if emulator/admin not available)."""
    try:
        if USE_EMULATOR:
            # Emulator usually accepts the same transport; credentials can be a mock
            creds = Mock(spec=google.auth.credentials.Credentials)
            client = FirestoreAdminClient(credentials=creds)
        else:
            client = FirestoreAdminClient()
        return client
    except Exception as e:
        info(f"FirestoreAdminClient unavailable/skipping admin steps: {e}")
        return None

async def get_async_admin_client_if_possible():
    try:
        if USE_EMULATOR:
            creds = Mock(spec=google.auth.credentials.Credentials)
            client = FirestoreAdminAsyncClient(credentials=creds)
        else:
            client = FirestoreAdminAsyncClient()
        return client
    except Exception as e:
        info(f"FirestoreAdminAsyncClient unavailable/skipping admin steps: {e}")
        return None

# -----------------------
# Test cases
# -----------------------
def test_new_config_sync_flow():
    info("\n=== new Configuration API: sync flow ===")
    # register a default configuration (use mock creds for emulator)
    mock_creds = Mock(spec=google.auth.credentials.Credentials)

    # default config
    configuration.add(prefix="app-", project="my-project")

    # extra config
    configuration.add(name="billing", prefix="billing-", project="billing-project")

    # get clients
    client = configuration.get_client()                  # sync client for "(default)"
    # async_client = configuration.get_async_client()      # async client for "(default)"
    billing_client = configuration.get_client("billing") # sync client for "billing"

    class Billing(Model):
        __db_config__ = "billing"
        __collection__ = "billing_accounts"
        billing_id: str
        name: str

    # cleanup
    cleanup_sync_collection_by_model(Billing)

    # create and save
    b = Billing(billing_id="9901981", name="Firedantic Billing")
    b.save()
    print(f"billing.id after save: {b.id}")
    assert_or_exit(b.id is not None, "Billing save did not set id")

    # reload
    b.reload()
    assert_or_exit(b.billing_id == "9901981", "billing_id mismatch after reload")

    # find
    results = Billing.find({"name": "Firedantic Billing"})
    assert_or_exit(isinstance(results, list), "find returned not a list")
    assert_or_exit(any(r.billing_id == "9901981" for r in results), "find did not return saved billing account")

    # delete
    b.delete()
    time.sleep(0.1)  # allow emulator a bit of time to delete
    remaining = Billing.find({"billing_id": "9901981"})
    assert_or_exit(all(r.company_id != "9901981" for r in remaining), "delete failed")

    print("new config sync flow OK")


def test_legacy_config_sync_flow():
    info("\n=== legacy configure() sync flow ===")
    # legacy configure() should still populate CONFIGURATIONS and work
    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    # create a sync Client for legacy configure
    if USE_EMULATOR:
        client = Client(project="legacy-project", credentials=mock_creds)
    else:
        client = Client()

    configure(client, prefix="legacy-sync-")
    assert_or_exit(CONFIGURATIONS["prefix"].startswith("legacy-sync-"), "legacy configure prefix mismatch")

    # use same model pattern as earlier
    class LegacyOwner(Model):
        first_name: str
        last_name: str

    class LegacyCompany(Model):
        __collection__ = "companies"
        company_id: str
        owner: LegacyOwner

    # cleanup and run
    cleanup_sync_collection_by_model(LegacyCompany)
    o = LegacyOwner(first_name="L", last_name="User")
    comp = LegacyCompany(company_id="L-1", owner=o)
    comp.save()
    comp.reload()
    assert_or_exit(comp.company_id == "L-1", "legacy reload failed")
    comp.delete()
    info("legacy sync flow OK")


async def test_new_config_async_flow():
    info("\n=== new Configuration API: async flow ===")
    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    configuration.add(prefix="integ-async-", project="test-project", credentials=mock_creds)

    class Owner(AsyncModel):
        first_name: str
        last_name: str

    class Company(AsyncModel):
        __collection__ = "companies"
        company_id: str
        owner: Owner

    await cleanup_async_collection_by_model(Company)

    owner = Owner(first_name="Alice", last_name="Smith")
    c = Company(company_id="A-1", owner=owner)
    await c.save()
    print(f"company.id after save: {c.id}")
    assert_or_exit(c.id is not None, "async save didn't set id")

    await c.reload()
    assert_or_exit(c.company_id == "A-1", "async reload company_id mismatch")
    assert_or_exit(c.owner.first_name == "Alice", "async owner first name mismatch")

    found = await Company.find({"company_id": "A-1"})
    assert_or_exit(len(found) >= 1 and found[0].company_id == "A-1", "async find failed")

    await c.delete()
    remains = await Company.find({"company_id": "A-1"})
    assert_or_exit(all(x.company_id != "A-1" for x in remains), "async delete failed")

    print("new config async flow OK")



async def test_legacy_config_async_flow():
    info("\n=== legacy configure() async flow ===")
    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    # create async client and call legacy configure
    if USE_EMULATOR:
        aclient = AsyncClient(project="legacy-project", credentials=mock_creds)
    else:
        aclient = AsyncClient()
    # legacy configure supports AsyncClient and sets CONFIGURATIONS
    configure(aclient, prefix="legacy-async-")
    assert_or_exit(CONFIGURATIONS["prefix"].startswith("legacy-async-"), "legacy async configure failed")

    class LOwner(AsyncModel):
        first_name: str
        last_name: str

    class LCompany(AsyncModel):
        __collection__ = "companies"
        company_id: str
        owner: LOwner

    await cleanup_async_collection_by_model(LCompany)
    o = LOwner(first_name="LA", last_name="User")
    c = LCompany(company_id="LA-1", owner=o)
    await c.save()
    await c.reload()
    assert_or_exit(c.company_id == "LA-1", "legacy async reload failed")
    await c.delete()
    info("legacy async flow OK")

def test_subcollections_and_model_for():
    info("\n=== subcollections (model_for) ===")
    # ensure configuration exists
    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    configuration.add(prefix="sc-", project="test-project", credentials=mock_creds)

    class Parent(Model):
        __collection__ = "parents"
        name: str

    class Stats(Model):
        __collection__ = None  # will be supplied via Collection
        __document_id__ = "id"
        purchases: int = 0

        class Collection:
            __collection_tpl__ = "parents/{id}/stats"

    # create parent and get submodel
    cleanup_sync_collection_by_model(Parent)
    p = Parent(name="P1")
    p.save()
    # build subcollection model class for parent
    StatsCollection = type("StatsForParent", (Stats,), {})
    # attach collection tpl like library would; simpler: use provided pattern via utility in README (model_for pattern)
    # Here we emulate model_for behavior:
    StatsCollection.__collection_cls__ = Stats.Collection
    StatsCollection.__collection__ = Stats.Collection.__collection_tpl__.format(id=p.id)
    StatsCollection.__document_id__ = "id"

    s = StatsCollection(purchases=3)
    s.save()
    # find back
    found = StatsCollection.find({"purchases": 3})
    assert_or_exit(any(x.purchases == 3 for x in found), "subcollection save/find failed")
    # cleanup
    for x in StatsCollection.find({}):
        x.delete()
    for x in Parent.find({}):
        x.delete()
    info("subcollections OK")

def test_transactions_sync():
    info("\n=== sync transactions ===")
    # mock_creds = Mock(spec=google.auth.credentials.Credentials)
    
    # Configure once
    configuration.add(
        project="firedantic-test",
        prefix="firedantic-test-",
    )
    
    class City(Model):
        __collection__ = "cities"
        population: int = 0

        def increment_population(self, increment: int = 1):
            @transactional
            def _increment_population(transaction: Transaction) -> None:
                self.reload(transaction=transaction)
                self.population += increment
                self.save(transaction=transaction)

            t = get_transaction()
            _increment_population(transaction=t)

    # cleanup
    cleanup_sync_collection_by_model(City)

    @transactional
    def decrement_population(
        transaction: Transaction, city: City, decrement: int = 1
    ):
        city.reload(transaction=transaction)
        city.population = max(0, city.population - decrement)
        city.save(transaction=transaction)

    # create object
    c = City(id="SF", population=1)
    c.save()

    c.increment_population(increment=2)
    assert c.population == 3

    t = get_transaction()
    decrement_population(transaction=t, city=c, decrement=1)
    assert c.population == 2

    # reload
    c.reload()
    assert_or_exit(c.population == 2, "sync transaction increment failed")
    
    # delete
    c.delete()
    print("sync transactions OK")

async def test_transactions_async():
    info("\n=== async transactions ===")
    
    # Configure once
    configuration.add(
        project="async-tx-test",
        prefix="async-tx-test-",
    )

    class CityA(AsyncModel):
        __collection__ = "cities"
        population: int = 0

    await cleanup_async_collection_by_model(CityA)

    @async_transactional
    async def increment_async(tx, city_id: str, inc: int = 1):
        c = await CityA.get_by_id(city_id, transaction=tx)
        c.population += inc
        await c.save(transaction=tx)

    # create ans save object
    c = CityA(id="AC1", population=2)
    await c.save()

    # increment with transaction
    t = get_async_transaction()
    await increment_async(transaction=t, city_id=c.id, inc=3)

    # reload
    await c.reload()
    assert_or_exit(c.population == 5, "async transaction failed")

    # delete
    await c.delete()
    print("async transactions OK")

def test_multi_config_usage():
    info("\n=== multi-config usage ===")

    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    
    # default config
    configuration.add(prefix="multi-default-", project="proj-default", credentials=mock_creds)
    
    # billing config
    configuration.add(name="billing", prefix="multi-billing-", project="proj-billing", credentials=mock_creds)

    class CompanyDefault(Model):
        __collection__ = "companies"
        company_id: str

    class BillingAccount(Model):
        __db_config__ = "billing"
        __collection__ = "billing_accounts"
        billing_id: str
        name: str

    # cleanup
    cleanup_sync_collection_by_model(CompanyDefault)
    cleanup_sync_collection_by_model(BillingAccount)

    # save to default
    cd = CompanyDefault(company_id="MD-1")
    cd.save()
    cd.reload()
    assert_or_exit(cd.company_id == "MD-1", "default config save/reload failed")

    # save to billing (model defines __db_config__)
    ba = BillingAccount(billing_id="B-1", name="Bill Co")
    ba.save()  # should use billing config
    ba.reload()
    assert_or_exit(ba.billing_id == "B-1", "billing model save/reload failed")

    # find calls (default vs billing)
    found_default = CompanyDefault.find({"company_id": "MD-1"})
    found_billing = BillingAccount.find({"billing_id": "B-1"})
    assert_or_exit(any(x.company_id == "MD-1" for x in found_default), "find default failed")
    assert_or_exit(any(x.billing_id == "B-1" for x in found_billing), "find billing failed")

    # cleanup
    cleanup_sync_collection_by_model(CompanyDefault)
    cleanup_sync_collection_by_model(BillingAccount)
    info("multi-config usage OK")

def test_indexes_and_ttl_sync():
    info("\n=== composite indexes and TTL (sync) ===")

    admin_client = get_admin_client_if_possible()
    if not admin_client:
        info("Skipping sync index/TTL setup (admin client not available).")
        return

    class ExpiringModel(Model):  ## uses "(default)" config name
        __collection__ = "expiringModel"
        __ttl_field__ = "expire"
        __composite_indexes__ = [
            collection_index(IndexField("content", Query.ASCENDING), IndexField("expire", Query.DESCENDING)),
            collection_group_index(IndexField("content", Query.DESCENDING), IndexField("expire", Query.ASCENDING)),
        ]
        content: str
        expire: datetime

    # register config with admin client (best-effort)
    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    configuration.add(prefix="idx-sync-", project="proj-idx", credentials=mock_creds, client=None, async_client=None, admin_client=admin_client)

    try:
        # call setup function (may require admin permission; emulator may accept)
        project = configuration.get_config().project
        if not USE_EMULATOR:
            # real GCP -> try to set up indexes
            set_up_composite_indexes_and_ttl_policies(gcloud_project=project, models=get_all_subclasses(Model))
            info("sync index/ttl setup called (no exception)")
        else:
            # emulator -> skip (or log)
            print("Skipping index/TTL setup when using emulator.")

    except Exception as e:
        info(f"index/ttl setup raised (will continue): {e}")

async def test_indexes_and_ttl_async():
    info("\n=== composite indexes and TTL (async) ===")
    admin_client = await get_async_admin_client_if_possible()
    if not admin_client:
        info("Skipping async index/TTL setup (async admin client not available).")
        return

    class ExpiringAsync(AsyncModel):
        __collection__ = "expiringModel"
        __ttl_field__ = "expire"
        __composite_indexes__ = [
            collection_index(IndexField("content", Query.ASCENDING), IndexField("expire", Query.DESCENDING)),
        ]
        content: str
        expire: datetime

    mock_creds = Mock(spec=google.auth.credentials.Credentials)
    configuration.add(prefix="idx-async-", project="proj-idx", credentials=mock_creds)

    try:
        project = configuration.get_config().project
        if not USE_EMULATOR:
            # real GCP -> try to set up indexes
            await async_set_up_composite_indexes_and_ttl_policies(gcloud_project=project, models=get_all_subclasses(AsyncModel))
            info("async index/ttl setup called (no exception)")
        else:
            # emulator -> skip (or log)
            print("Skipping index/TTL setup when using emulator.")
        
    except Exception as e:
        info(f"async index/ttl setup raised (will continue): {e}")

# -----------------------
# Runner
# -----------------------
def main():
    info("Beginning full integration test following README examples")
    if not USE_EMULATOR:
        info("WARNING: FIRESTORE_EMULATOR_HOST not set — this script is designed for emulator runs; continue with caution.")

    # run sync new config flow
    test_new_config_sync_flow()

    # legacy sync flow
    test_legacy_config_sync_flow()

    # run async new config flow
    asyncio.run(test_new_config_async_flow()) ## Currently deletion fails!

    # legacy async flow
    asyncio.run(test_legacy_config_async_flow())

    # subcollections
    test_subcollections_and_model_for()

    # transactions
    test_transactions_sync()
    asyncio.run(test_transactions_async())

    # multi-config usage
    test_multi_config_usage()

    # indexes & ttl (sync & async) (best-effort)
    test_indexes_and_ttl_sync()
    asyncio.run(test_indexes_and_ttl_async())

    info("\nIntegration README full test finished successfully.")

if __name__ == "__main__":
    main()
