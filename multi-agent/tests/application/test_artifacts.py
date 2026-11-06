"""Artifact policy uses only the application-owned storage contract."""

from unittest.mock import create_autospec

import pytest
from mas.application.artifacts.access_models import ArtifactActor
from mas.application.artifacts.ports import (
    ArtifactIntegrityError,
    ArtifactLimitExceeded,
    ArtifactMissing,
    ArtifactRepository,
)
from mas.application.artifacts.service import ArtifactService
from mas.core.identity import Identity
from support.artifacts import chunks, publication


@pytest.fixture
def artifact_policy():
    repository = create_autospec(ArtifactRepository, instance=True)
    repository.put.side_effect = lambda record, content: record
    return ArtifactService(repository, max_bytes=16), repository


async def test_publication_identity_is_stable_and_scoped_by_owner_type(artifact_policy):
    service, _ = artifact_policy
    owners = (Identity.user("same"), Identity.user("same", "New name"), Identity.team("same"))
    records = [
        await service.publish(publication(), chunks(), ArtifactActor(owner)) for owner in owners
    ]
    assert records[0].reference == records[1].reference
    assert records[0].reference != records[2].reference
    assert records[0].matches(records[1])


async def test_byte_admission_happens_before_storage(artifact_policy):
    service, repository = artifact_policy
    with pytest.raises(ArtifactLimitExceeded):
        await service.publish(
            publication(b"x" * 17), chunks(b"x" * 17), ArtifactActor(Identity.user("owner"))
        )
    repository.put.assert_not_awaited()


@pytest.mark.parametrize("mismatch", [False, True], ids=["foreign-owner", "wrong-content"])
async def test_lineage_is_authorized_and_bound_to_exact_content(artifact_policy, mismatch):
    service, repository = artifact_policy
    owner = ArtifactActor(Identity.user("owner"))
    source = await service.publish(publication(), chunks(), owner)
    repository.put.reset_mock()
    repository.get.return_value = source
    reference = source.reference
    if mismatch:
        reference = reference.model_copy(update={"sha256": "0" * 64})
    with pytest.raises(ArtifactIntegrityError if mismatch else ArtifactMissing):
        await service.publish(
            publication(key="derived", inputs=(reference,)),
            chunks(),
            owner if mismatch else ArtifactActor(Identity.team("owner")),
        )
    repository.put.assert_not_awaited()


async def test_content_access_checks_owner_before_opening_storage(artifact_policy):
    service, repository = artifact_policy
    record = await service.publish(publication(), chunks(), ArtifactActor(Identity.user("owner")))
    repository.get.return_value = record
    with pytest.raises(ArtifactMissing):
        async with service.open(record.reference, ArtifactActor(Identity.user("other"))):
            pytest.fail("Foreign content was opened")
    repository.open.assert_not_called()
