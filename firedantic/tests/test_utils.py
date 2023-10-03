from firedantic import AsyncModel, Model, get_all_subclasses
from firedantic.tests.tests_async.conftest import ExpiringModel as AsyncExpiringModel
from firedantic.tests.tests_sync.conftest import ExpiringModel as SyncExpiringModel


def test_get_all_subclasses():
    async_subclasses = get_all_subclasses(AsyncModel)
    assert AsyncExpiringModel in async_subclasses
    assert SyncExpiringModel not in async_subclasses

    sync_subclasses = get_all_subclasses(Model)
    assert SyncExpiringModel in sync_subclasses
    assert AsyncExpiringModel not in sync_subclasses
