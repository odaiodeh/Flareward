"""Retirement persists before cancellation and never converts uncertainty to closure."""

import asyncio

import pytest
from support.check_jobs import assert_pending_job_queries, check_job_scenario
from support.check_runs import source_request

from flareward.services.access.executions import ExecutionAccessUnavailable
from flareward.services.verification.check_ports import StartCheckRun
from flareward.services.verification.domain.check_runs import CheckJobState, CheckRunStatus
from flareward.services.verification.domain.models import CheckRequirement


async def started(case, key="candidate"):
    plan = (await case.verification.start(source_request(key), case.actor)).state.plan
    run = await case.service.start(
        StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), case.actor
    )
    return plan, run


async def test_cancelled_plan_retains_pending_job_until_terminal_and_survives_reconstruction():
    case = check_job_scenario()
    plan, run = await started(case)
    await case.verification.cancel(plan.plan_id, case.actor)
    await case.maintenance().reconcile()
    pending = await case.repository.get(run.intent_id)
    assert pending.job_state == CheckJobState.RETIRING and not pending.evidence_recorded
    await case.service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), case.actor)
    assert case.driver.submissions == 1
    case.control.terminal = True
    await case.maintenance().reconcile()
    closed = await case.service.refresh(run.intent_id, case.actor)
    assert closed.job_state == CheckJobState.CLOSED and not closed.evidence_recorded
    assert (await case.verification.inspect(plan.plan_id, case.actor)).outcome == "cancelled"


async def test_closed_owning_root_cancels_the_plan_without_workflow_polling():
    case = check_job_scenario()
    plan, run = await started(case)
    case.roots.ended, case.control.terminal = True, True
    await case.maintenance().reconcile()
    assert (await case.repository.get(run.intent_id)).job_state == CheckJobState.CLOSED
    assert (await case.verification.inspect(plan.plan_id, case.actor)).outcome == "cancelled"


async def test_expired_plan_stops_jobs_without_unknown_root_authority(monkeypatch):
    case = check_job_scenario()
    _, run = await started(case)
    case.clock.advance(3601)
    case.control.terminal = True

    async def unavailable(*args):
        raise ExecutionAccessUnavailable()

    monkeypatch.setattr(case.roots, "closed", unavailable)
    await case.maintenance().reconcile()
    assert (await case.repository.get(run.intent_id)).job_state == CheckJobState.CLOSED


async def test_unknown_root_authority_never_cancels_live_work(monkeypatch):
    case = check_job_scenario()
    _, run = await started(case)

    async def unavailable(*args):
        raise ExecutionAccessUnavailable()

    monkeypatch.setattr(case.roots, "closed", unavailable)
    await case.maintenance().reconcile()
    assert (await case.repository.get(run.intent_id)).job_state == CheckJobState.ACTIVE
    assert not case.control.calls


async def test_accepted_receipts_are_preserved_during_job_retirement():
    case = check_job_scenario()
    plan, run = await started(case)
    case.driver.complete()
    completed = await case.service.refresh(run.intent_id, case.actor)
    evidence = (await case.verification.inspect(plan.plan_id, case.actor)).state.evidence
    case.control.terminal = True
    await case.maintenance().reconcile()
    retired = await case.repository.get(run.intent_id)
    assert retired.job_state == CheckJobState.CLOSED and retired.evidence_recorded
    assert retired.observation == completed.observation
    assert (await case.verification.inspect(plan.plan_id, case.actor)).state.evidence == evidence


async def test_late_provider_acknowledgement_cannot_bypass_retirement(monkeypatch):
    case = check_job_scenario()
    entered, release = asyncio.Event(), asyncio.Event()
    original = case.driver.submit

    async def delayed(run):
        entered.set()
        await release.wait()
        return await original(run)

    monkeypatch.setattr(case.driver, "submit", delayed)
    plan = (await case.verification.start(source_request(), case.actor)).state.plan
    request = StartCheckRun(plan_id=plan.plan_id, runner="checks@1")
    task = asyncio.create_task(case.service.start(request, case.actor))
    try:
        await entered.wait()
        await case.verification.cancel(plan.plan_id, case.actor)
        await case.maintenance().reconcile()
    finally:
        release.set()
        run = await task
    assert run.job_state == CheckJobState.RETIRING and run.observation is None
    case.control.terminal = True
    await case.maintenance().reconcile()
    assert (await case.repository.get(run.intent_id)).job_state == CheckJobState.CLOSED
    assert case.driver.submissions == 1


async def test_paging_advances_past_unavailable_jobs_and_retries_after_reconstruction():
    case = check_job_scenario()
    records = [await started(case, key) for key in ("one", "two")]
    for plan, _ in records:
        await case.verification.cancel(plan.plan_id, case.actor)
    first, second = sorted((run for _, run in records), key=lambda run: run.intent_id)
    case.control.unavailable.add(first.intent_id)
    case.control.terminal = True
    maintenance = case.maintenance()
    await maintenance.reconcile(limit=1)
    await maintenance.reconcile(limit=1)
    assert (await case.repository.get(first.intent_id)).job_state == CheckJobState.RETIRING
    assert (await case.repository.get(second.intent_id)).job_state == CheckJobState.CLOSED
    case.control.unavailable.clear()
    await case.maintenance().reconcile()
    assert (await case.repository.get(first.intent_id)).job_state == CheckJobState.CLOSED


async def test_ready_job_retirement_fences_submission_before_any_provider_effect(monkeypatch):
    case = check_job_scenario()
    entered, release = asyncio.Event(), asyncio.Event()
    original = case.repository.save

    async def delayed(run, *, expected_revision):
        if run.status == CheckRunStatus.UNCERTAIN:
            entered.set()
            await release.wait()
        return await original(run, expected_revision=expected_revision)

    monkeypatch.setattr(case.repository, "save", delayed)
    plan = (await case.verification.start(source_request(), case.actor)).state.plan
    task = asyncio.create_task(
        case.service.start(StartCheckRun(plan_id=plan.plan_id, runner="checks@1"), case.actor)
    )
    try:
        await entered.wait()
        await case.verification.cancel(plan.plan_id, case.actor)
        await case.maintenance().reconcile()
    finally:
        release.set()
        run = await task
    assert run.job_state == CheckJobState.CLOSED
    assert not case.driver.submissions and not case.control.calls


async def test_changed_binding_cannot_retire_through_a_different_provider():
    case = check_job_scenario()
    plan, run = await started(case)
    await case.verification.cancel(plan.plan_id, case.actor)
    case.driver.configuration_digest = "b" * 64
    await case.maintenance().reconcile()
    assert (await case.repository.get(run.intent_id)).job_state == CheckJobState.RETIRING
    assert not case.control.calls


async def test_memory_pending_job_queries_follow_the_shared_repository_contract():
    await assert_pending_job_queries(check_job_scenario())


@pytest.mark.parametrize("partial", [False, True])
async def test_retirement_recovers_evidence_already_committed_before_lost_ack(monkeypatch, partial):
    extra = (CheckRequirement(check="other@1", verifiers=frozenset({"other"})),) if partial else ()
    case = check_job_scenario(extra_checks=extra)
    plan, run = await started(case)
    case.driver.complete()
    entered, release = asyncio.Event(), asyncio.Event()
    original = case.repository.save

    async def delayed(record, *, expected_revision):
        if record.evidence_recorded and record.job_state == CheckJobState.ACTIVE:
            entered.set()
            await release.wait()
        return await original(record, expected_revision=expected_revision)

    monkeypatch.setattr(case.repository, "save", delayed)
    task = asyncio.create_task(case.service.refresh(run.intent_id, case.actor))
    try:
        await entered.wait()
        evidence = (await case.verification.inspect(plan.plan_id, case.actor)).state.evidence
        case.control.terminal = True
        await case.maintenance().reconcile()
    finally:
        release.set()
        result = await task
    assert result.job_state == CheckJobState.CLOSED and result.evidence_recorded
    assert (await case.verification.inspect(plan.plan_id, case.actor)).state.evidence == evidence
    assert case.driver.submissions == 1
