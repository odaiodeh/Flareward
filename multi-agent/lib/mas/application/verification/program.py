"""Reusable, bounded verification waiting through the existing runtime port."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from mas.application.programs.ports import ProgramRuntime
from mas.application.programs.registry import ApplicationRegistration
from mas.application.verification.check_ports import CheckRunHandle
from mas.application.verification.models import VerificationView
from mas.application.verification.operations import VerificationHandle
from mas.domain.check_runs import CheckRun, CheckRunStatus
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.verification import VerificationOutcome


class AwaitVerificationConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    inspection: ElementBundle
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    poll_interval_seconds: float = Field(default=5, ge=0.1, le=3600, allow_inf_nan=False)
    max_polls: int = Field(default=120, ge=1, le=10_000)


class VerificationWaitReason(StrEnum):
    RESOLVED = "resolved"
    POLL_LIMIT = "poll_limit"


class VerificationWaitResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    verification: VerificationView
    reason: VerificationWaitReason
    polls: int = Field(ge=1)


class CheckWaitResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    check: CheckRun
    reason: VerificationWaitReason
    polls: int = Field(ge=1)


async def await_verification(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, AwaitVerificationConfig)
    try:
        handle = VerificationHandle.model_validate(inputs)
    except ValidationError:
        raise ValueError("Verification wait input violates its contract") from None
    for index in range(config.max_polls):
        result = await runtime.invoke_element(
            config.inspection,
            handle.model_dump(mode="json"),
            key=f"inspect-{index}",
            execution=config.execution,
        )
        try:
            view = VerificationView.model_validate(result)
        except ValidationError:
            raise ValueError("Verification inspection violates its contract") from None
        if view.state.plan.plan_id != handle.plan_id:
            raise ValueError("Verification inspection identifies a different plan")
        resolved = view.outcome != VerificationOutcome.PENDING
        if resolved or index + 1 == config.max_polls:
            return VerificationWaitResult(
                verification=view,
                polls=index + 1,
                reason=VerificationWaitReason.RESOLVED
                if resolved
                else VerificationWaitReason.POLL_LIMIT,
            ).model_dump(mode="json")
        await runtime.sleep(config.poll_interval_seconds)
    raise AssertionError("Verification polling requires a positive limit")


async def await_check_run(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, AwaitVerificationConfig)
    try:
        handle = CheckRunHandle.model_validate(inputs)
    except ValidationError:
        raise ValueError("Check wait input violates its contract") from None
    for index in range(config.max_polls):
        result = await runtime.invoke_element(
            config.inspection,
            handle.model_dump(mode="json"),
            key=f"refresh-{index}",
            execution=config.execution,
        )
        try:
            run = CheckRun.model_validate(result)
        except ValidationError:
            raise ValueError("Check inspection violates its contract") from None
        if run.intent_id != handle.intent_id:
            raise ValueError("Check inspection identifies a different intent")
        resolved = run.status == CheckRunStatus.REJECTED or run.evidence_recorded
        if resolved or index + 1 == config.max_polls:
            return CheckWaitResult(
                check=run,
                polls=index + 1,
                reason=VerificationWaitReason.RESOLVED
                if resolved
                else VerificationWaitReason.POLL_LIMIT,
            ).model_dump(mode="json")
        await runtime.sleep(config.poll_interval_seconds)
    raise AssertionError("Check polling requires a positive limit")


APPLICATION_PROGRAMS = (
    ApplicationRegistration("await_verification", "1", AwaitVerificationConfig, await_verification),
    ApplicationRegistration("await_check_run", "1", AwaitVerificationConfig, await_check_run),
)
