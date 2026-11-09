"""Actual database contracts; opt in with FLAREWARD_TEST_MONGO_URI."""

import asyncio
import os
from datetime import UTC, datetime, timedelta

import pytest
from runengine.adapters.coordination.config import LocalHostConfig
from support.elements import element_registry
from support.execution_claims import assert_submission_claim_contract
from support.session_store_contracts import assert_query_and_delete_contracts

from flareward.bootstrap.platform import compose_platform
from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.executions.adapters.mongo.execution_repository import MongoExecutionRepository
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.models import ExecutionPhase, ExecutionRecord, SubmissionState
from flareward.executions.models import PreparedExecution, SubmissionClaim
from flareward.executions.ports import ExecutionLocationUnavailable
from flareward.programs.domain.models import ApplicationDefinition, ProgramDefinition, ProgramRef
from flareward.services.identity.domain import Identity
from flareward.services.sessions.adapters.mongo.session_store import MongoSessionStore
from flareward.services.sessions.domain.status import SessionStatus
from flareward.services.sessions.execution.program_sessions import (
    CreateProgramSession,
    StartSessionTurn,
)
from flareward.services.sessions.records import SessionRecord


async def test_mongo_session_queries_and_guarded_deletion(mongo_database):
    store = MongoSessionStore(mongo_database)
    await store.initialize()
    await assert_query_and_delete_contracts(store)


@pytest.mark.integration
async def test_mongo_execution_admission_identity_and_terminal_fence(mongo_database):
    repository = MongoExecutionRepository(mongo_database)
    owner = Identity.user("owner")
    record = ExecutionRecord(
        execution_id="run",
        owner=owner,
        program=ProgramRef(program_id="test", revision=1),
        inputs={},
        context=ExecutionContext(identity=owner),
    )
    assert await repository.create(record)
    assert not await repository.create(record)
    await repository.update(
        record.model_copy(update={"phase": ExecutionPhase.COMPLETED, "result": {}})
    )
    await repository.update(record.model_copy(update={"phase": ExecutionPhase.RUNNING}))
    assert (await repository.get("run")).phase == ExecutionPhase.COMPLETED
    with pytest.raises(ValueError, match="identity"):
        await repository.update(record.model_copy(update={"inputs": {"changed": True}}))


@pytest.mark.integration
async def test_mongo_prepared_snapshot_claim_and_pre_submission_cancellation(mongo_database):
    repository = MongoExecutionRepository(mongo_database)
    owner = Identity.user("owner")
    record = ExecutionRecord(
        execution_id="prepared",
        owner=owner,
        program=ProgramRef(program_id="test", revision=1),
        inputs={},
        context=ExecutionContext(identity=owner, engine_handle="private-run"),
    )
    snapshot = PreparedExecution(format="test/1", payload_json='{"frozen": true}')
    assert await repository.create(record, snapshot)
    now = datetime.now(UTC)
    claim = SubmissionClaim(token="a" * 32, expires_at=now + timedelta(seconds=30))
    claims = await asyncio.gather(
        *(repository.claim_submission("prepared", claim, now=now) for _ in range(5))
    )
    assert claims.count(True) == 1
    assert await repository.get_prepared("prepared") == snapshot
    assert not await repository.cancel_prepared("prepared")
    cancelled = record.model_copy(update={"execution_id": "cancelled"})
    assert await repository.create(cancelled, snapshot)
    assert await repository.cancel_prepared("cancelled")
    assert not await repository.claim_submission("cancelled", claim, now=now)
    assert (await repository.get("cancelled")).phase == ExecutionPhase.CANCELLED


@pytest.mark.integration
async def test_mongo_admission_claims_fence_stale_updates_and_preserve_cancel_intent(
    mongo_database,
):
    await assert_submission_claim_contract(MongoExecutionRepository(mongo_database))


async def test_mongo_session_admission_and_legacy_document_compatibility(mongo_database):
    store = MongoSessionStore(mongo_database)
    await store.initialize()
    owner = Identity.user("owner")
    legacy = SessionRecord(
        run_id="legacy",
        identity=owner,
        blueprint_id="blueprint",
        run_context=ExecutionContext(identity=owner, session_id="legacy"),
    )
    # Documents already in workflow_sessions do not carry the new concurrency field.
    document = legacy.model_dump(mode="json", exclude={"version", "program"})
    await mongo_database.workflow_sessions.insert_one(document)
    loaded = await store.get("legacy")
    assert loaded.version == 0 and loaded.program is None
    changes = [
        loaded.model_copy(update={"version": 1, "active_execution_id": str(i)}) for i in range(5)
    ]
    accepted = await asyncio.gather(
        *(store.replace(value, expected_version=0) for value in changes)
    )
    assert accepted.count(True) == 1
    stale = loaded.model_copy(update={"version": 1, "status": SessionStatus.COMPLETED})
    assert not await store.replace(stale, expected_version=0)
    assert len(await store.list(owner)) == 1
    assert await store.list(Identity.user("other")) == []


@pytest.mark.integration
async def test_mongo_lifespan_reconciles_session_and_retains_result_across_restart(mongo_database):
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        interactions="disabled",
        authentication="development",
        development_user="owner",
        mongo_uri=os.environ["FLAREWARD_TEST_MONGO_URI"],
        mongo_database=mongo_database.name,
        application_modules=("support.programs",),
        reconcile_interval=0.05,
    )
    owner = Identity.user("owner")
    async with compose_platform(settings, elements=element_registry()) as services:
        leaf = ProgramDefinition(
            program_id="persistent-leaf",
            name="Persistent leaf",
            owner=owner,
            implementation=ApplicationDefinition(implementation="greeting", version="1"),
        )
        await services.programs.save(leaf, owner)
        leaf_revision = await services.programs.publish(
            leaf.program_id,
            owner,
            expected_version=(await services.programs.draft(leaf.program_id, owner)).version,
        )
        definition = ProgramDefinition(
            program_id="persistent",
            name="Persistent",
            owner=owner,
            implementation=ApplicationDefinition(
                implementation="composed", version="1", children={"greet": leaf_revision.reference}
            ),
        )
        await services.programs.save(definition, owner)
        revision = await services.programs.publish(
            "persistent",
            owner,
            expected_version=(await services.programs.draft("persistent", owner)).version,
        )
        session = await services.sessions.create(
            CreateProgramSession(program=revision.reference), owner
        )
        submitted = await services.sessions.start(
            session.run_id,
            StartSessionTurn(inputs={"name": "stored"}, execution_id="persisted-turn"),
            owner,
        )
        async with asyncio.timeout(5):
            while True:
                current = await services.sessions.get(session.run_id, owner)
                if current.status == SessionStatus.COMPLETED:
                    break
                await asyncio.sleep(0.01)
        assert current.last_result == {"answer": "hello stored"}
        assert submitted.active_execution_id == "persisted-turn"
        children = await services.executions.children("persisted-turn", owner)
        assert len(children) == 1
        child_id = children[0].execution_id
        assert children[0].parent_execution_id == "persisted-turn"
        assert children[0].session_id == session.run_id
    # A fresh Local host has no retained native runs. Application results are durable in Mongo.
    async with compose_platform(settings, elements=element_registry()) as restarted:
        current = await restarted.sessions.refresh(session.run_id, owner)
        execution = await restarted.executions.result("persisted-turn", owner)
        assert current.last_result == execution.result == {"answer": "hello stored"}
        children = await restarted.executions.children("persisted-turn", owner)
        assert [child.execution_id for child in children] == [child_id]
        assert (await restarted.executions.result(child_id, owner)).result == execution.result


async def test_fresh_local_host_preserves_unreachable_active_record_and_can_shut_down(
    mongo_database,
):
    owner = Identity.user("owner")
    original = ExecutionRecord(
        execution_id="old-local-run",
        owner=owner,
        program=ProgramRef(program_id="old-program", revision=1),
        inputs={},
        context=ExecutionContext(identity=owner, engine_handle="old-native-id"),
        location="runengine:local:previous-instance",
        phase=ExecutionPhase.RUNNING,
        submission=SubmissionState.ACCEPTED,
    )
    repository = MongoExecutionRepository(mongo_database)
    await repository.create(original)
    settings = PlatformSettings(
        host=LocalHostConfig(),
        storage="mongo",
        interactions="disabled",
        authentication="development",
        development_user="owner",
        mongo_uri=os.environ["FLAREWARD_TEST_MONGO_URI"],
        mongo_database=mongo_database.name,
        application_modules=("support.programs",),
    )
    async with compose_platform(settings, elements=element_registry()) as services:
        assert await services.executions.get(original.execution_id, owner) == original
        with pytest.raises(ExecutionLocationUnavailable):
            await services.executions.refresh(original.execution_id, owner)
    assert await repository.get(original.execution_id) == original
