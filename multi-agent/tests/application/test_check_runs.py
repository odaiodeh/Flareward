"""Application intent reservation, borrowed wait authority and evidence recovery."""

import asyncio
from unittest.mock import create_autospec

import pytest
from mas.application.verification.access_models import (
    VerificationAccessScope,
    VerificationAction,
    VerificationActor,
)
from mas.application.verification.check_ports import (
    CheckSubmissionRejected,
    ResolveCheckRun,
    StartCheckRun,
)
from mas.application.verification.check_service import CheckRunService
from mas.application.verification.ports import (
    VerificationConflict,
    VerificationMissing,
    VerificationStorageError,
)
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRunStatus
from mas.domain.verification import CheckVerdict, VerificationOutcome
from support.check_runs import (
    MemoryCheckRunRepository,
    ScriptedCheckRunner,
    check_registration,
    source_policy,
    source_request,
)
from support.verification import MemoryVerificationRepository, VerificationClock


@pytest.fixture
async def scenario():
    owner, clock = Identity.user("owner"), VerificationClock()
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": source_policy(owner)}, clock=clock
    )
    actor = VerificationActor(
        owner,
        VerificationAccessScope(
            root_execution_id="root",
            policies=frozenset({"source@1"}),
            actions=frozenset(
                {
                    VerificationAction.CREATE,
                    VerificationAction.READ,
                    VerificationAction.CANCEL,
                    VerificationAction.RUN_CHECK,
                }
            ),
        ),
    )
    plan = (await verification.start(source_request(), actor)).state.plan
    driver, repository = ScriptedCheckRunner(), MemoryCheckRunRepository()
    service = CheckRunService(
        repository, verification, {"checks@1": check_registration(owner, driver)}, clock=clock
    )
    return owner, clock, actor, plan, driver, repository, verification, service


async def test_concurrent_calls_and_lost_acknowledgement_never_repeat_submission(scenario):
    owner, clock, actor, plan, driver, repository, verification, service = scenario
    driver.lose_acknowledgement = True
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    results = await asyncio.gather(*(service.start(request, actor) for _ in range(20)))
    assert driver.submissions == 1
    assert len({result.intent_id for result in results}) == 1
    recovered = CheckRunService(
        repository, verification, {"checks@1": check_registration(owner, driver)}, clock=clock
    )
    driver.complete()
    completed = await recovered.start(request, actor)
    assert completed.status == CheckRunStatus.COMPLETED and completed.evidence_recorded
    assert (await verification.inspect(plan.plan_id, actor)).outcome == VerificationOutcome.ACCEPTED
    assert await recovered.refresh(completed.intent_id, actor) == completed
    assert driver.submissions == 1


async def test_absent_provider_run_stays_uncertain_instead_of_retrying(scenario):
    _, _, actor, plan, driver, _, _, service = scenario
    driver.lose_acknowledgement = True
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    result = await service.start(request, actor)
    driver.observation = None
    for _ in range(3):
        assert (await service.start(request, actor)).status == CheckRunStatus.UNCERTAIN
    assert driver.submissions == 1 and "private" not in result.model_dump_json()


@pytest.mark.parametrize(
    "verdict,outcome",
    [
        (CheckVerdict.PASSED, VerificationOutcome.ACCEPTED),
        (CheckVerdict.FAILED, VerificationOutcome.REJECTED),
        (CheckVerdict.ERROR, VerificationOutcome.ERROR),
    ],
)
async def test_trusted_terminal_verdict_controls_acceptance(scenario, verdict, outcome):
    _, _, actor, plan, driver, _, verification, service = scenario
    result = await service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), actor)
    driver.complete(verdict)
    result = await service.refresh(result.intent_id, actor)
    assert result.evidence_recorded
    view = await verification.inspect(plan.plan_id, actor)
    assert view.outcome == outcome
    assert view.state.evidence[0].run_id == "trusted-ci:1"


async def test_workflow_without_check_authority_cannot_dispatch_or_refresh(scenario):
    owner, _, actor, plan, driver, _, _, service = scenario
    read_only = VerificationActor(
        owner, actor.scope.model_copy(update={"actions": frozenset({VerificationAction.READ})})
    )
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    with pytest.raises(PermissionError):
        await service.start(request, read_only)
    result = await service.start(request, actor)
    with pytest.raises(PermissionError):
        await service.refresh(result.intent_id, read_only)
    with pytest.raises(VerificationMissing):
        await service.refresh(result.intent_id, VerificationActor(Identity.user("other")))
    other_root = VerificationActor(
        owner, actor.scope.model_copy(update={"root_execution_id": "other"})
    )
    with pytest.raises(VerificationMissing):
        await service.refresh(result.intent_id, other_root)
    assert driver.submissions == 1


async def test_cancelled_or_expired_plan_never_admits_another_submission(scenario):
    _, clock, actor, plan, driver, _, verification, service = scenario
    await verification.cancel(plan.plan_id, actor)
    with pytest.raises(VerificationConflict):
        await service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), actor)
    fresh = (await verification.start(source_request("fresh"), actor)).state.plan
    clock.advance(3601)
    with pytest.raises(VerificationConflict):
        await service.start(StartCheckRun(plan_id=fresh.plan_id, runner="checks@1"), actor)
    assert driver.submissions == 0


async def test_cancellation_during_submission_preserves_uncertainty(scenario):
    _, _, actor, plan, driver, _, _, service = scenario
    mocked = create_autospec(ScriptedCheckRunner, instance=True)
    mocked.submit.side_effect = asyncio.CancelledError()
    driver.submit = mocked.submit
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    with pytest.raises(asyncio.CancelledError):
        await service.start(request, actor)
    result = await service.start(request, actor)
    assert result.status == CheckRunStatus.UNCERTAIN
    assert mocked.submit.await_count == 1


async def test_definitive_rejection_is_retained_without_duplicate_effect(scenario):
    _, _, actor, plan, driver, _, _, service = scenario
    mocked = create_autospec(ScriptedCheckRunner, instance=True)
    mocked.submit.side_effect = CheckSubmissionRejected("private provider refusal")
    driver.submit = mocked.submit
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    result = await service.start(request, actor)
    assert result.status == CheckRunStatus.REJECTED
    assert await service.start(request, actor) == result
    assert mocked.submit.await_count == 1


async def test_changed_binding_does_not_reinterpret_an_admitted_intent(scenario):
    _, _, actor, plan, driver, _, _, service = scenario
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    await service.start(request, actor)
    driver.configuration_digest = "c" * 64
    with pytest.raises(VerificationConflict, match="configuration changed"):
        await service.start(request, actor)
    assert driver.submissions == 1


async def test_lost_evidence_acknowledgement_recovers_the_same_immutable_receipt(scenario):
    _, _, actor, plan, driver, repository, verification, service = scenario
    run = await service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), actor)
    driver.complete()
    repository.fail_evidence_acknowledgement = True
    with pytest.raises(VerificationStorageError):
        await service.refresh(run.intent_id, actor)
    assert len((await verification.inspect(plan.plan_id, actor)).state.evidence) == 1
    repository.fail_evidence_acknowledgement = False
    restored = await service.refresh(run.intent_id, actor)
    assert restored.evidence_recorded and driver.submissions == 1
    assert len((await verification.inspect(plan.plan_id, actor)).state.evidence) == 1


async def test_human_resolution_attaches_a_confirmed_run_and_records_an_idempotent_audit(scenario):
    owner, _, actor, plan, driver, _, verification, service = scenario
    driver.lose_acknowledgement = True
    run = await service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), actor)
    request = ResolveCheckRun(
        key="attach-1",
        expected_revision=run.revision,
        external_id="trusted-ci:1",
        reason="Located the existing provider job",
    )
    results = await asyncio.gather(
        *(service.resolve(run.intent_id, request, owner, owner) for _ in range(5))
    )
    assert all(result.resolution.issued_by.owns(owner) for result in results)
    assert all(result.resolution.reason == request.reason for result in results)
    assert driver.submissions == 1
    driver.complete()
    completed = await service.refresh(run.intent_id, actor)
    assert completed.evidence_recorded
    assert await service.resolve(run.intent_id, request, owner, owner) == completed
    with pytest.raises(VerificationConflict):
        await service.resolve(
            run.intent_id, request.model_copy(update={"key": "another-intent"}), owner, owner
        )
    assert (await verification.inspect(plan.plan_id, actor)).outcome == VerificationOutcome.ACCEPTED


async def test_resolution_rejects_stale_foreign_or_unconfirmed_provider_references(scenario):
    owner, _, actor, plan, driver, _, _, service = scenario
    driver.lose_acknowledgement = True
    run = await service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), actor)
    request = ResolveCheckRun(
        key="attach-1",
        expected_revision=run.revision,
        external_id="trusted-ci:1",
        reason="Located the existing provider job",
    )
    with pytest.raises(VerificationConflict):
        await service.resolve(
            run.intent_id, request.model_copy(update={"expected_revision": 0}), owner, owner
        )
    with pytest.raises(VerificationConflict):
        await service.resolve(
            run.intent_id, request.model_copy(update={"external_id": "other:2"}), owner, owner
        )
    with pytest.raises(VerificationMissing):
        await service.resolve(
            run.intent_id, request, Identity.user("other"), Identity.user("other")
        )
    with pytest.raises(PermissionError):
        await service.resolve(run.intent_id, request, owner, Identity.team("owner"))
    assert await service.inspect(run.intent_id, actor) == run
    assert driver.submissions == 1
