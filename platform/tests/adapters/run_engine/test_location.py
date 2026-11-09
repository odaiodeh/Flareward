"""Coordinator placement identity covers routing and native submission policy."""

import pytest
from pydantic import ValidationError
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig

from flareward.executions.adapters.run_engine.outbound.location import host_location
from flareward.executions.models import PreparedExecution


@pytest.mark.parametrize(
    "changes",
    [
        {"endpoint": "another-cluster:7233"},
        {"namespace": "another-namespace"},
        {"task_queue": "another-queue"},
        {"delivery_max_attempts": 5},
        {"invocation_timeout_seconds": 10.0},
    ],
)
def test_coordinator_changes_cannot_share_submission_identity(changes):
    config = TemporalHostConfig()
    assert host_location(config) == host_location(config.model_copy(deep=True))
    assert host_location(config) != host_location(config.model_copy(update=changes))


def test_identical_local_configuration_does_not_claim_another_hosts_work():
    config = LocalHostConfig()
    assert host_location(config) != host_location(config)


def test_prepared_snapshot_digest_covers_location():
    snapshot = PreparedExecution(
        format="test/1", payload_json='{"immutable": true}', location="original"
    )
    changed = snapshot.model_dump()
    changed["location"] = "changed"
    with pytest.raises(ValidationError, match="digest mismatch"):
        PreparedExecution.model_validate(changed)
