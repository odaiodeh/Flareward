"""Pinned verifier authority, uncertain dispatch and exact-candidate report contracts."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import create_autospec

import pytest
from support.artifacts import chunks, inline_artifact
from support.check_runs import check_policy, source_policy, source_request
from support.program_checks import verifier_definition
from support.program_interfaces import declared_interface
from support.verification import MemoryVerificationRepository, VerificationClock

from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import ExecutionFailure, ExecutionPhase, ExecutionRecord
from lumora.executions.ports import SubmissionUnconfirmed
from lumora.programs.domain.models import ProgramRevision
from lumora.services.identity.domain import Identity
from lumora.services.verification.access_models import VerificationActor
from lumora.services.verification.check_ports import CheckProviderUnavailable
from lumora.services.verification.domain.check_runs import CheckRun, CheckRunStatus
from lumora.services.verification.program_checks import (
    CheckProgramArtifacts,
    CheckProgramExecutions,
    CheckProgramResult,
    CheckProgramRevisions,
    ProgramCheckConfiguration,
    ProgramCheckRunner,
)
from lumora.services.verification.service import VerificationService


@pytest.fixture
async def scenario():
    owner, operator, clock = Identity.user("owner"), Identity.user("verifier"), VerificationClock()
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": source_policy(owner)}, clock=clock
    )
    plan = (await verification.start(source_request(), VerificationActor(owner))).state.plan
    revision = ProgramRevision(
        definition=verifier_definition(operator),
        revision=1,
        interface=declared_interface(verifier_definition(operator)),
    )
    config = ProgramCheckConfiguration(
        policy=check_policy(owner),
        program_owner=operator,
        program=revision.reference,
        content_digest=revision.content_digest,
    )
    executions = create_autospec(CheckProgramExecutions, instance=True)
    programs = create_autospec(CheckProgramRevisions, instance=True)
    programs.revision.return_value = revision
    driver = ProgramCheckRunner(config, executions, programs)
    run = CheckRun(
        intent_id="c" * 64,
        plan=plan,
        check=config.policy.check,
        verifier=config.policy.verifier,
        runner="program@1",
        configuration_digest=driver.configuration_digest,
        created_at=clock(),
    )
    identity = "verification-" + run.intent_id
    result = CheckProgramResult(subject_fingerprint=plan.subject.fingerprint, verdict="passed")
    record = ExecutionRecord(
        execution_id=identity,
        owner=operator,
        program=revision.reference,
        content_digest=revision.content_digest,
        inputs={
            "intent_id": run.intent_id,
            "plan_id": plan.plan_id,
            "check": run.check,
            "subject": plan.subject.model_dump(mode="json"),
        },
        context=ExecutionContext(
            identity=operator, execution_id=identity, root_execution_id=identity
        ),
        phase="completed",
        submission="accepted",
        result=result.model_dump(mode="json"),
    )
    executions.start.return_value = record
    executions.refresh.return_value = record
    return config, executions, programs, driver, run, record


async def test_lost_start_acknowledgement_reconciles_without_repeating_start(scenario):
    config, executions, _, driver, run, record = scenario
    executions.start.side_effect = SubmissionUnconfirmed(
        ExecutionFailure(kind="infrastructure", message="private transport detail")
    )
    with pytest.raises(CheckProviderUnavailable, match="unconfirmed") as error:
        await driver.submit(run)
    assert "private" not in str(error.value)
    observation = await driver.reconcile(run)
    assert observation.status == CheckRunStatus.COMPLETED and observation.verdict == "passed"
    executions.start.assert_awaited_once()
    request, caller = executions.start.await_args.args
    assert caller == config.program_owner and not request.workflow_access
    assert request.execution_id == record.execution_id
    assert request.inputs == record.inputs
    executions.refresh.side_effect = KeyError("missing")
    assert await driver.reconcile(run) is None
    executions.start.assert_awaited_once()


async def test_changed_trust_binding_never_starts_or_attests(scenario):
    _, executions, programs, driver, run, _ = scenario
    programs.revision.return_value = programs.revision.return_value.model_copy(
        update={"content_digest": "b" * 64}
    )
    with pytest.raises(CheckProviderUnavailable):
        await driver.submit(run)
    with pytest.raises(CheckProviderUnavailable):
        await driver.reconcile(run)
    executions.start.assert_not_awaited()
    executions.refresh.assert_not_awaited()


@pytest.mark.parametrize(
    "change",
    [
        {"content_digest": "b" * 64},
        {"execution_id": "unrelated"},
        {"owner": Identity.user("other")},
        {"inputs": {}},
        {"result": {"subject_fingerprint": "b" * 64, "verdict": "passed"}},
        {"result": {"subject_fingerprint": "a" * 64, "verdict": "passed", "private": True}},
        {"result": {"details": "x" * 65_536}},
    ],
)
async def test_foreign_or_malformed_execution_cannot_attest(scenario, change):
    _, executions, _, driver, run, record = scenario
    executions.refresh.return_value = record.model_copy(update=change)
    with pytest.raises(CheckProviderUnavailable):
        await driver.reconcile(run)


@pytest.mark.parametrize("phase", [ExecutionPhase.FAILED, ExecutionPhase.CANCELLED])
async def test_failed_verifier_reports_error_without_raw_diagnostics(scenario, phase):
    _, executions, _, driver, run, record = scenario
    executions.refresh.return_value = record.model_copy(
        update={
            "phase": phase,
            "failure": ExecutionFailure(kind="application", message="private candidate bytes"),
        }
    )
    assert (await driver.reconcile(run)).verdict == "error"
    source = (await driver.list(run))[0]
    async with driver.open(run, source) as chunks:
        report = b"".join([chunk async for chunk in chunks])
    assert b"private" not in report and phase.value.encode() in report


async def test_reports_reconstruct_from_execution_and_reject_changed_manifest(scenario):
    config, executions, programs, driver, run, _ = scenario
    sources = await driver.list(run)
    reconstructed = ProgramCheckRunner(config, executions, programs)
    assert await reconstructed.list(run) == sources
    async with reconstructed.open(run, sources[0]) as chunks:
        report = b"".join([chunk async for chunk in chunks])
    assert CheckProgramResult.model_validate_json(report).verdict == "passed"
    wrong = sources[0].model_copy(update={"name": "different.json"})
    with pytest.raises(CheckProviderUnavailable):
        async with driver.open(run, wrong):
            pytest.fail("Changed report was accepted")
    executions.start.assert_not_awaited()


async def test_cancellation_propagates_instead_of_becoming_an_outcome(scenario):
    _, executions, _, driver, run, _ = scenario
    executions.start.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await driver.submit(run)


async def test_job_stop_requires_terminal_observation_not_cancel_acknowledgement(scenario):
    config, executions, _, driver, run, record = scenario
    running = record.model_copy(update={"phase": ExecutionPhase.RUNNING, "result": None})
    executions.refresh.return_value = running
    assert await driver.stop(run) is False
    executions.cancel.assert_awaited_once_with(record.execution_id, config.program_owner)
    executions.refresh.return_value = record.model_copy(update={"phase": ExecutionPhase.CANCELLED})
    assert await driver.stop(run) is True
    executions.refresh.side_effect = KeyError("missing")
    assert await driver.stop(run) is False


async def test_job_stop_rejects_foreign_execution_before_cancellation(scenario):
    _, executions, _, driver, run, record = scenario
    executions.refresh.return_value = record.model_copy(update={"content_digest": "b" * 64})
    with pytest.raises(CheckProviderUnavailable):
        await driver.stop(run)
    executions.cancel.assert_not_awaited()


async def test_inline_transport_cannot_be_configured_for_an_unrelated_subject(scenario):
    config = scenario[0]
    with pytest.raises(ValueError, match="blob artifact policy"):
        ProgramCheckConfiguration.model_validate(
            {
                **config.model_dump(mode="json"),
                "input_artifact_max_bytes": 64,
            }
        )


@pytest.mark.parametrize("content", [b"candidate", b"wrong"])
async def test_inline_candidate_transport_uses_owned_exact_bytes_and_no_receiver_grant(
    scenario, content
):
    config, executions, programs, _, run, record = scenario
    artifact = inline_artifact()
    subject = run.plan.subject.model_copy(
        update={
            "kind": "blob-artifact@1",
            "identity": artifact.reference.model_dump(mode="json"),
        }
    )
    config = config.model_copy(
        update={
            "policy": config.policy.model_copy(update={"subject_kind": "blob-artifact@1"}),
            "input_artifact_max_bytes": 64,
        }
    )
    run = run.model_copy(
        update={
            "plan": run.plan.model_copy(update={"subject": subject}),
            "configuration_digest": config.digest,
        }
    )
    artifacts = create_autospec(CheckProgramArtifacts, instance=True)

    @asynccontextmanager
    async def source():
        yield chunks(content)

    artifacts.open.return_value = source()
    driver = ProgramCheckRunner(config, executions, programs, artifacts=artifacts)

    async def start(request, caller):
        observed = record.model_copy(
            update={
                "inputs": request.inputs,
                "result": CheckProgramResult(
                    subject_fingerprint=subject.fingerprint, verdict="passed"
                ).model_dump(mode="json"),
            }
        )
        executions.refresh.return_value = observed
        return observed

    executions.start.side_effect = start
    if content == b"wrong":
        with pytest.raises(CheckProviderUnavailable):
            await driver.submit(run)
        executions.start.assert_not_awaited()
    else:
        assert (await driver.submit(run)).verdict == "passed"
        assert (await driver.reconcile(run)).verdict == "passed"
        artifacts.open.assert_called_once()
        reference, actor = artifacts.open.call_args.args
        assert reference == artifact.reference and actor.identity == run.plan.owner
        request = executions.start.await_args.args[0]
        assert not request.workflow_access
        assert request.inputs["artifact"] == artifact.model_dump(mode="json")
