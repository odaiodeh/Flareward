"""Actual Mongo grants share the application lifecycle and server-clock expiry fence."""

from datetime import timedelta

from support.artifact_workflow import ArtifactWorkflowCase, managed_artifact_lifecycle

from flareward.services.access.adapters.mongo.artifact_workflow_access import (
    MongoArtifactWorkflowRepository,
)


async def test_managed_artifact_mongo_lifecycle(mongo_database):
    repository = MongoArtifactWorkflowRepository(mongo_database)
    await repository.initialize()
    await managed_artifact_lifecycle(ArtifactWorkflowCase.create(repository))


async def test_artifact_authentication_requires_live_database_clock(mongo_database):
    repository = MongoArtifactWorkflowRepository(mongo_database)
    await repository.initialize()
    case = ArtifactWorkflowCase.create(repository)
    case.clock.now -= timedelta(seconds=61)
    reservation, _ = await case.provision()
    assert await repository.get(reservation.grant_id) is not None
    assert await repository.get(reservation.grant_id, active_at=case.clock()) is None
