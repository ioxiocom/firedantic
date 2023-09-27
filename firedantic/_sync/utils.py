from logging import getLogger
from typing import Iterable

from google.cloud.firestore_admin_v1.services.firestore_admin import (
    FirestoreAdminClient,
)
from google.cloud.firestore_admin_v1.types.field import Field

from firedantic._sync.model import TBareModel

logger = getLogger("firedantic")


def set_up_ttl_policies(
    gcloud_project: str,
    models: Iterable[TBareModel],
    database: str = "(default)",
):
    client = FirestoreAdminClient()

    for model in models:
        if not model.__ttl_field__:
            continue

        logger.debug(
            'Checking TTL config for "%s", collection: %s, field: "%s"',
            model.__name__,
            model.get_collection_name(),
            model.__ttl_field__,
        )

        path = client.field_path(
            project=gcloud_project,
            database=database,
            collection=model.get_collection_name(),
            field=model.__ttl_field__,
        )
        field_obj = client.get_field({"name": path})

        # Variables for logging
        readable_state = str(field_obj.ttl_config.state).removeprefix("State.")
        log_str = '"%s", collection: "%s", field: "%s", state: "%s"'
        log_params = [
            model.__name__,
            model.get_collection_name(),
            model.__ttl_field__,
            readable_state,
        ]

        if field_obj.ttl_config.state == Field.TtlConfig.State.STATE_UNSPECIFIED:
            logger.info("Setting up new TTL config: " + log_str, *log_params)
            field_obj.ttl_config = Field.TtlConfig(
                {"state": Field.TtlConfig.State.CREATING}
            )
            client.update_field({"field": field_obj})
        elif field_obj.ttl_config.state == Field.TtlConfig.State.CREATING:
            logger.info("TTL config is still being created: " + log_str, *log_params)
        elif field_obj.ttl_config.state == Field.TtlConfig.State.NEEDS_REPAIR:
            logger.error("TTL config needs repair: " + log_str, *log_params)
        elif field_obj.ttl_config.state == Field.TtlConfig.State.ACTIVE:
            logger.debug("TTL config is active: " + log_str, *log_params)
