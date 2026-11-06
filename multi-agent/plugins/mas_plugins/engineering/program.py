"""A bounded Engineering Program using scoped verification and human review effects."""

from enum import StrEnum
from typing import Self

from mas.application.programs.composition.scope import ChildCalls
from mas.application.programs.ports import ChildContract, ChildExecution, ProgramRuntime
from mas.application.programs.registry import ApplicationRegistration
from mas.application.reviews.program import HumanReviewConfig, HumanReviewResult, human_review
from mas.application.verification.check_ports import CheckRunHandle, StartCheckRun
from mas.application.verification.models import VerificationView
from mas.application.verification.operations import RequestVerification, VerificationHandle
from mas.core.enums import ResourceCategory
from mas.domain.check_runs import CheckRun, CheckRunStatus
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import PathBinding
from mas.domain.reviews import ReviewDecision, ReviewResponse, ReviewStatus
from mas.domain.verification import CheckEvidence, VerificationOutcome, VerificationSubject
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator


class EngineeringInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    task: JsonValue


class EngineeringFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    candidate: VerificationSubject
    verification: VerificationOutcome
    evidence: tuple[CheckEvidence, ...] = Field(default=(), max_length=32)
    review: ReviewResponse | None = None


class EngineeringWork[Task = JsonValue](BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    task: Task
    attempt: int = Field(ge=0)
    feedback: EngineeringFeedback | None = None


class EngineeringCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    subject: VerificationSubject


class EngineeringOutcome(StrEnum):
    VERIFIED = "verified"
    REPAIRS_EXHAUSTED = "repairs_exhausted"
    CHECK_UNRESOLVED = "check_unresolved"
    CHECK_REFUSED = "check_refused"
    VERIFICATION_CLOSED = "verification_closed"
    REVIEW_UNRESOLVED = "review_unresolved"
    REVIEW_CLOSED = "review_closed"


class EngineeringResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    outcome: EngineeringOutcome
    candidate: VerificationSubject
    attempts: int = Field(ge=1)
    verification: VerificationView
    review: HumanReviewResult | None = None

    @model_validator(mode="after")
    def exact_candidate_outcome(self) -> Self:
        if self.verification.state.plan.subject.fingerprint != self.candidate.fingerprint:
            raise ValueError("Engineering result must identify the exact verified candidate")
        record = self.review.review if self.review is not None else None
        if record is not None and record.specification.subject != self.candidate.model_dump(
            mode="json"
        ):
            raise ValueError("Engineering result must identify the exact reviewed candidate")
        if self.outcome == EngineeringOutcome.VERIFIED and (
            self.verification.outcome != VerificationOutcome.ACCEPTED
            or record is None
            or record.status != ReviewStatus.DECIDED
            or record.response is None
            or record.response.decision != ReviewDecision.APPROVE
        ):
            raise ValueError("Verified Engineering requires accepted checks and human approval")
        return self


def validate_result[T: BaseModel](model: type[T], value: JsonValue) -> T:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise ValueError("Engineering effect violates its contract") from None


def require_service_operation(bundle: ElementBundle, operation: str, service: str) -> None:
    """Require the installed scoped adapter, not an arbitrary lookalike operation."""
    root = next(entry for entry in bundle.entries if entry.resource.key == bundle.root)
    by_key = {entry.resource.key: entry for entry in bundle.entries}
    if (
        root.resource.key.category != ResourceCategory.OPERATION
        or root.resource.type_key != operation
        or len(root.dependencies) != 1
        or by_key[root.dependencies[0]].resource.key.category != ResourceCategory.PROVIDER
        or by_key[root.dependencies[0]].resource.type_key != service
        or len(bundle.entries) != 2
    ):
        raise ValueError("Engineering authority requires the registered scoped service operation")


class EngineeringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    implementation: str = Field(default="implementation", min_length=1, max_length=128)
    repair: str = Field(default="repair", min_length=1, max_length=128)
    max_repairs: int = Field(default=2, ge=0, le=20)
    verification_policy: str = Field(min_length=1, max_length=128)
    runners: tuple[str, ...] = Field(min_length=1, max_length=32)
    request_verification: ElementBundle
    inspect_verification: ElementBundle
    start_check: ElementBundle
    refresh_check: ElementBundle
    review: HumanReviewConfig
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    poll_interval_seconds: float = Field(default=5, ge=0.1, le=3600, allow_inf_nan=False)
    max_polls: int = Field(default=120, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_authorities(self) -> Self:
        if len(set(self.runners)) != len(self.runners) or any(
            not runner for runner in self.runners
        ):
            raise ValueError("Engineering runners must be nonempty and unique")
        for bundle, operation in (
            (self.request_verification, "request_verification"),
            (self.inspect_verification, "inspect_verification"),
            (self.start_check, "start_verification_check"),
            (self.refresh_check, "refresh_verification_check"),
        ):
            require_service_operation(bundle, operation, "verification_service")
        require_service_operation(self.review.opener, "open_human_review", "review_service")
        require_service_operation(self.review.inspection, "inspect_human_review", "review_service")
        return self

    def child_contracts(self) -> dict[str, ChildContract]:
        contract = ChildContract(
            scope_schema=EngineeringWork.model_json_schema(),
            outputs={"subject": PathBinding(path=("subject",))},
            result_model=EngineeringCandidate,
        )
        children = {self.implementation: contract}
        if self.max_repairs:
            children[self.repair] = contract
        return children


class AttemptRuntime:
    """Namespace review effects so each iteration has its own durable occurrence."""

    def __init__(self, runtime: ProgramRuntime, attempt: int) -> None:
        self._runtime, self._prefix = runtime, f"attempt-{attempt}-"

    @property
    def execution_id(self) -> str:
        return self._runtime.execution_id

    async def invoke_element(
        self,
        bundle: ElementBundle,
        inputs: JsonValue,
        *,
        key: str,
        execution: ExecutionSelection | None = None,
    ) -> JsonValue:
        return await self._runtime.invoke_element(
            bundle, inputs, key=self._prefix + key, execution=execution
        )

    async def start_child(
        self,
        name: str,
        inputs: JsonValue,
        *,
        key: str,
        environment_imports: dict[str, str] | None = None,
    ) -> ChildExecution:
        return await self._runtime.start_child(
            name, inputs, key=self._prefix + key, environment_imports=environment_imports
        )

    async def receive(self, name: str, *, timeout: float | None = None) -> JsonValue:
        return await self._runtime.receive(name, timeout=timeout)

    async def sleep(self, seconds: float) -> None:
        await self._runtime.sleep(seconds)


class EngineeringCoordinator:
    def __init__(self, runtime: ProgramRuntime, config: EngineeringConfig) -> None:
        self._runtime, self._config = runtime, config

    async def _invoke(self, bundle: ElementBundle, value: BaseModel, key: str) -> JsonValue:
        return await self._runtime.invoke_element(
            bundle, value.model_dump(mode="json"), key=key, execution=self._config.execution
        )

    async def _verification(
        self, candidate: VerificationSubject, attempt: int
    ) -> tuple[VerificationView, EngineeringOutcome | None]:
        prefix = f"attempt-{attempt}"
        view = validate_result(
            VerificationView,
            await self._invoke(
                self._config.request_verification,
                RequestVerification(subject=candidate, policy=self._config.verification_policy),
                f"{prefix}-request",
            ),
        )
        if (
            view.state.plan.subject.fingerprint != candidate.fingerprint
            or view.state.plan.policy != self._config.verification_policy
        ):
            raise ValueError("Verification identifies different work")
        plan = view.state.plan.plan_id
        checks: list[CheckRun] = []
        if view.outcome == VerificationOutcome.PENDING:
            for index, runner in enumerate(self._config.runners):
                check = validate_result(
                    CheckRun,
                    await self._invoke(
                        self._config.start_check,
                        StartCheckRun(plan_id=plan, runner=runner),
                        f"{prefix}-start-{index}",
                    ),
                )
                if check.plan.plan_id != plan or check.runner != runner:
                    raise ValueError("Check identifies different work")
                checks.append(check)
        for poll in range(self._config.max_polls):
            for index, check in enumerate(checks):
                if check.status == CheckRunStatus.REJECTED:
                    return view, EngineeringOutcome.CHECK_REFUSED
                if not check.evidence_recorded:
                    updated = validate_result(
                        CheckRun,
                        await self._invoke(
                            self._config.refresh_check,
                            CheckRunHandle(intent_id=check.intent_id),
                            f"{prefix}-refresh-{poll}-{index}",
                        ),
                    )
                    if updated.intent_id != check.intent_id or updated.plan.plan_id != plan:
                        raise ValueError("Check inspection identifies different work")
                    if updated.status == CheckRunStatus.REJECTED:
                        return view, EngineeringOutcome.CHECK_REFUSED
                    checks[index] = updated
            view = validate_result(
                VerificationView,
                await self._invoke(
                    self._config.inspect_verification,
                    VerificationHandle(plan_id=plan),
                    f"{prefix}-inspect-{poll}",
                ),
            )
            if (
                view.state.plan.plan_id != plan
                or view.state.plan.subject.fingerprint != candidate.fingerprint
                or view.state.plan.policy != self._config.verification_policy
            ):
                raise ValueError("Verification inspection identifies different work")
            if view.outcome != VerificationOutcome.PENDING:
                return view, None
            if poll + 1 < self._config.max_polls:
                await self._runtime.sleep(self._config.poll_interval_seconds)
        return view, EngineeringOutcome.CHECK_UNRESOLVED

    async def run(self, request: EngineeringInput) -> EngineeringResult:
        feedback: EngineeringFeedback | None = None
        async with ChildCalls(self._runtime) as calls:
            for attempt in range(self._config.max_repairs + 1):
                work = EngineeringWork(task=request.task, attempt=attempt, feedback=feedback)
                _, value = await calls.call(
                    self._config.implementation if attempt == 0 else self._config.repair,
                    work.model_dump(mode="json"),
                    key=f"attempt-{attempt}-work",
                )
                try:
                    candidate = EngineeringCandidate.model_validate(value).subject
                except ValidationError:
                    raise ValueError(
                        "Engineering child did not return a candidate identity"
                    ) from None
                view, unresolved = await self._verification(candidate, attempt)
                review = None
                outcome = unresolved
                if outcome is None and view.outcome == VerificationOutcome.ACCEPTED:
                    review = validate_result(
                        HumanReviewResult,
                        await human_review(
                            AttemptRuntime(self._runtime, attempt),
                            candidate.model_dump(mode="json"),
                            self._config.review,
                        ),
                    )
                    record = review.review
                    if record.status == ReviewStatus.DECIDED and record.response is not None:
                        decision = record.response.decision
                        if decision == ReviewDecision.APPROVE:
                            outcome = EngineeringOutcome.VERIFIED
                    elif record.status == ReviewStatus.PENDING:
                        outcome = EngineeringOutcome.REVIEW_UNRESOLVED
                    else:
                        outcome = EngineeringOutcome.REVIEW_CLOSED
                elif outcome is None and view.outcome not in {
                    VerificationOutcome.REJECTED,
                    VerificationOutcome.ERROR,
                }:
                    outcome = EngineeringOutcome.VERIFICATION_CLOSED
                if outcome is None and attempt == self._config.max_repairs:
                    outcome = EngineeringOutcome.REPAIRS_EXHAUSTED
                if outcome is not None:
                    return EngineeringResult(
                        outcome=outcome,
                        candidate=candidate,
                        attempts=attempt + 1,
                        verification=view,
                        review=review,
                    )
                feedback = EngineeringFeedback(
                    candidate=candidate,
                    verification=view.outcome,
                    evidence=view.state.evidence,
                    review=review.review.response if review is not None else None,
                )
        raise AssertionError("Engineering requires at least one attempt")


async def engineering(runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel) -> JsonValue:
    assert isinstance(config, EngineeringConfig)
    return (
        await EngineeringCoordinator(runtime, config).run(validate_result(EngineeringInput, inputs))
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "engineering",
        "1",
        EngineeringConfig,
        engineering,
        input_model=EngineeringInput,
        result_model=EngineeringResult,
    ),
)
