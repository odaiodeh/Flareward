"""The reusable wait program observes recorded results and delegates timers to its runtime."""

import asyncio
from unittest.mock import create_autospec

import pytest
from mas.application.programs.ports import ProgramRuntime
from mas.application.verification.access_models import VerificationActor
from mas.application.verification.models import VerificationView
from mas.application.verification.program import (
    AwaitVerificationConfig,
    await_check_run,
    await_verification,
)
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRun, CheckRunObservation, CheckRunStatus
from mas.domain.verification import CheckVerdict
from pydantic import ValidationError
from support.operations import operation_bundle
from support.verification import (
    MemoryVerificationRepository,
    VerificationClock,
    evidence_request,
    verification_authority,
    verification_policy,
    verification_request,
)


@pytest.mark.parametrize("resolved", [True, False])
async def test_wait_uses_runtime_timers_and_distinguishes_poll_budget_from_acceptance(
    application, resolved
):
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    pending = await service.start(verification_request(), VerificationActor(owner))
    await service.submit(evidence_request(pending.state.plan), verification_authority(owner))
    accepted = await service.submit(
        evidence_request(pending.state.plan, "security@1"), verification_authority(owner, "scanner")
    )
    runtime = create_autospec(ProgramRuntime, instance=True)
    runtime.invoke_element.side_effect = [
        pending.model_dump(mode="json"),
        (accepted if resolved else pending).model_dump(mode="json"),
    ]
    config = AwaitVerificationConfig(
        inspection=operation_bundle(application.elements), max_polls=2, poll_interval_seconds=0.5
    )
    result = await await_verification(runtime, {"plan_id": pending.state.plan.plan_id}, config)
    assert result["reason"] == ("resolved" if resolved else "poll_limit")
    assert result["verification"]["outcome"] == ("accepted" if resolved else "pending")
    assert result["polls"] == 2
    runtime.sleep.assert_awaited_once_with(0.5)
    assert [call.kwargs["key"] for call in runtime.invoke_element.await_args_list] == [
        "inspect-0",
        "inspect-1",
    ]


async def test_cancelling_a_wait_does_not_cancel_the_borrowed_verification_plan(application):
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    pending = await service.start(verification_request(), VerificationActor(owner))
    runtime = create_autospec(ProgramRuntime, instance=True)
    runtime.invoke_element.return_value = pending.model_dump(mode="json")
    runtime.sleep.side_effect = asyncio.CancelledError()
    config = AwaitVerificationConfig(inspection=operation_bundle(application.elements), max_polls=2)
    with pytest.raises(asyncio.CancelledError):
        await await_verification(runtime, {"plan_id": pending.state.plan.plan_id}, config)
    assert runtime.invoke_element.await_count == 1
    assert await service.inspect(pending.state.plan.plan_id, VerificationActor(owner)) == pending


@pytest.mark.parametrize("claimed", ["accepted", "rejected", "error", "cancelled"])
async def test_pending_evidence_cannot_claim_a_terminal_evidence_outcome(claimed):
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    pending = await service.start(verification_request(), VerificationActor(owner))
    data = pending.model_dump(mode="json")
    data["outcome"] = claimed
    with pytest.raises(ValidationError, match="outcome does not match"):
        VerificationView.model_validate(data)


async def test_wait_rejects_acceptance_without_evidence(application):
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    pending = await service.start(verification_request(), VerificationActor(owner))
    data = pending.model_dump(mode="json")
    data["outcome"] = "accepted"
    runtime = create_autospec(ProgramRuntime, instance=True)
    runtime.invoke_element.return_value = data
    config = AwaitVerificationConfig(inspection=operation_bundle(application.elements))
    with pytest.raises(ValueError, match="inspection violates its contract"):
        await await_verification(runtime, {"plan_id": pending.state.plan.plan_id}, config)
    runtime.sleep.assert_not_awaited()


@pytest.mark.parametrize("verdict", [CheckVerdict.FAILED, CheckVerdict.ERROR])
async def test_unsuccessful_evidence_cannot_be_relabelled_as_accepted(verdict):
    owner, clock = Identity.user("owner"), VerificationClock()
    service = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    pending = await service.start(verification_request(), VerificationActor(owner))
    result = await service.submit(
        evidence_request(pending.state.plan, verdict=verdict), verification_authority(owner)
    )
    data = result.model_dump(mode="json")
    data["outcome"] = "accepted"
    with pytest.raises(ValidationError, match="outcome does not match"):
        VerificationView.model_validate(data)


@pytest.mark.parametrize("recorded", [False, True])
async def test_check_wait_requires_recorded_evidence_and_preserves_uncertainty(
    application, recorded
):
    owner, clock = Identity.user("owner"), VerificationClock()
    verification = VerificationService(
        MemoryVerificationRepository(), {"release@1": verification_policy(owner)}, clock=clock
    )
    plan = (await verification.start(verification_request(), VerificationActor(owner))).state.plan
    pending = CheckRun(
        intent_id="a" * 64,
        plan=plan,
        check="tests@1",
        runner="ci@1",
        verifier="ci",
        configuration_digest="b" * 64,
        created_at=clock(),
        status=CheckRunStatus.UNCERTAIN,
    )
    completed = pending.model_copy(
        update={
            "status": CheckRunStatus.COMPLETED,
            "observation": CheckRunObservation(
                external_id="ci:1", status=CheckRunStatus.COMPLETED, verdict=CheckVerdict.PASSED
            ),
            "evidence_recorded": recorded,
            "reports_collected": True,
            "report_sources": (),
        }
    )
    runtime = create_autospec(ProgramRuntime, instance=True)
    runtime.invoke_element.side_effect = [
        pending.model_dump(mode="json"),
        completed.model_dump(mode="json"),
    ]
    config = AwaitVerificationConfig(inspection=operation_bundle(application.elements), max_polls=2)
    result = await await_check_run(runtime, {"intent_id": pending.intent_id}, config)
    assert result["reason"] == ("resolved" if recorded else "poll_limit")
    assert result["polls"] == 2
    runtime.sleep.assert_awaited_once_with(5)
