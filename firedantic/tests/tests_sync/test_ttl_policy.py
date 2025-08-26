import pytest
from google.cloud.firestore_admin_v1 import Field

from firedantic import set_up_ttl_policies
from firedantic.tests.tests_sync.conftest import ExpiringModel


def test_set_up_ttl_policies_new_policy(mock_admin_client):
    result = set_up_ttl_policies(
        gcloud_project="fake-project", models=[ExpiringModel], client=mock_admin_client
    )
    # Ensure one TTL policy creation operation is triggered when setting up the fields
    assert len(result) == 1
    # Ensure the update field was called to set the state to creating
    assert (
        mock_admin_client.updated_field["field"].ttl_config.state
        == Field.TtlConfig.State.CREATING
    )


@pytest.mark.parametrize(
    "state",
    (
        [Field.TtlConfig.State.CREATING],
        [Field.TtlConfig.State.ACTIVE],
        [Field.TtlConfig.State.NEEDS_REPAIR],
    ),
)

def test_set_up_ttl_policies_other_states(mock_admin_client, state):
    mock_admin_client.field_state = Field.TtlConfig.State.ACTIVE
    result = set_up_ttl_policies(
        gcloud_project="fake-project", models=[ExpiringModel], client=mock_admin_client
    )
    # Ensure no TTL policy creation operation is triggered for this state
    assert len(result) == 0
    # Ensure no update action was done either
    assert mock_admin_client.updated_field is None
