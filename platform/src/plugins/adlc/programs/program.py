"""A bounded Engineering Program using scoped verification and human review effects."""

import json
from enum import StrEnum
from typing import Annotated, Self

from jsonschema import SchemaError
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    ValidationError,
    field_validator,
    model_validator,
)

from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.composition.scope import ChildCalls
from flareward.programs.domain.models import PathBinding
from flareward.programs.interfaces import BindingContractError, InterfaceContract
from flareward.programs.ports import ChildContract, ChildExecution, ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.resources.domain.bundles import ElementBundle
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.reviews.domain.models import ReviewDecision, ReviewResponse, ReviewStatus
from flareward.services.verification.check_ports import CheckRunHandle, StartCheckRun
from flareward.services.verification.domain.check_runs import CheckRun, CheckRunStatus
from flareward.services.verification.domain.models import (
    CheckEvidence,
    CheckRequirement,
    VerificationOutcome,
    VerificationSubject,
)
from flareward.services.verification.models import VerificationView
from plugins.adlc.programs.review import EngineeringReviewSubject
from plugins.human_review.programs.human_review import (
    HumanReviewConfig,
    HumanReviewResult,
    human_review,
)
from plugins.verification.elements.operations import (
    RequestVerification,
    VerificationHandle,
)

__runengine_contract__ = "flareward-engineering-v3"

type CompletionName = Annotated[str, Field(min_length=1, max_length=128)]


class EngineeringInput(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    task: JsonValue
    completion: CompletionName | None = None


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
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    outcome: EngineeringOutcome
    completion: CompletionName
    candidate: VerificationSubject
    attempts: int = Field(ge=1)
    verification: VerificationView
    review: HumanReviewResult | None = None

    @model_validator(mode="after")
    def exact_candidate_outcome(self) -> Self:
        if self.verification.state.plan.subject.fingerprint != self.candidate.fingerprint:
            raise ValueError("Engineering result must identify the exact verified candidate")
        record = self.review.review if self.review is not None else None
        if record is not None:
            subject = EngineeringReviewSubject(
                completion=self.completion, candidate=self.candidate, verification=self.verification
            )
            expected_review = record.specification.model_copy(
                update={"subject": subject.model_dump(mode="json")}
            )
            if record.specification.fingerprint != expected_review.fingerprint:
                raise ValueError("Engineering result must preserve the exact reviewed evidence")
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


class EngineeringCompletion(BaseModel):
    """One published choice of deliverable, producers, checks and human acceptance."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    name: CompletionName
    candidate_schema: dict[str, JsonValue]
    implementation: str = Field(default="implementation", min_length=1, max_length=128)
    repair: str = Field(default="repair", min_length=1, max_length=128)
    max_repairs: int = Field(default=2, ge=0, le=20)
    verification_policy: str = Field(min_length=1, max_length=128)
    requirements: tuple[CheckRequirement, ...] = Field(min_length=1, max_length=32)
    runners: tuple[str, ...] = Field(min_length=1, max_length=32)
    review: HumanReviewConfig

    @field_validator("candidate_schema")
    @classmethod
    def valid_candidate_schema(cls, schema: dict[str, JsonValue]) -> dict[str, JsonValue]:
        try:
            InterfaceContract.check_schema(schema)
        except SchemaError, BindingContractError, RecursionError:
            raise ValueError("Completion requires a valid bundled candidate schema") from None
        return schema

    @model_validator(mode="after")
    def valid_acceptance(self) -> Self:
        checks = [requirement.check for requirement in self.requirements]
        if len(set(checks)) != len(checks):
            raise ValueError("Completion requirements must name unique checks")
        if len(set(self.runners)) != len(self.runners) or any(
            not runner for runner in self.runners
        ):
            raise ValueError("Engineering runners must be nonempty and unique")
        require_service_operation(self.review.opener, "open_human_review", "review_service")
        require_service_operation(self.review.inspection, "inspect_human_review", "review_service")
        return self

    def validate_candidate(self, value: JsonValue) -> VerificationSubject:
        try:
            candidate = EngineeringCandidate.model_validate(value)
            InterfaceContract.root(self.candidate_schema).validate_value(value)
        except ValidationError, BindingContractError:
            raise ValueError("Engineering child violates the selected candidate contract") from None
        return candidate.subject


class EngineeringConfig(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    completions: tuple[EngineeringCompletion, ...] = Field(min_length=1, max_length=32)
    default_completion: CompletionName
    request_verification: ElementBundle
    inspect_verification: ElementBundle
    start_check: ElementBundle
    refresh_check: ElementBundle
    execution: ExecutionSelection = Field(default_factory=ExecutionSelection)
    poll_interval_seconds: float = Field(default=5, ge=0.1, le=3600, allow_inf_nan=False)
    max_polls: int = Field(default=120, ge=1, le=10_000)

    @model_validator(mode="after")
    def validate_authorities(self) -> Self:
        names = [completion.name for completion in self.completions]
        if len(names) != len(set(names)) or self.default_completion not in names:
            raise ValueError("Completion choices require unique names and a declared default")
        for bundle, operation in (
            (self.request_verification, "request_verification"),
            (self.inspect_verification, "inspect_verification"),
            (self.start_check, "start_verification_check"),
            (self.refresh_check, "refresh_verification_check"),
        ):
            require_service_operation(bundle, operation, "verification_service")
        self.child_contracts()
        return self

    def child_contracts(self) -> dict[str, ChildContract]:
        children: dict[str, ChildContract] = {}
        schemas: dict[str, str] = {}
        for completion in self.completions:
            contract = ChildContract(
                scope_schema=EngineeringWork.model_json_schema(),
                outputs={"subject": PathBinding(path=("subject",))},
                result_model=EngineeringCandidate,
                result_schema=completion.candidate_schema,
            )
            aliases = (
                (completion.implementation, completion.repair)
                if completion.max_repairs
                else (completion.implementation,)
            )
            for alias in aliases:
                schema = json.dumps(completion.candidate_schema, sort_keys=True, allow_nan=False)
                if alias in schemas and schemas[alias] != schema:
                    raise ValueError("A shared child alias requires the same candidate contract")
                schemas[alias], children[alias] = schema, contract
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
    def __init__(self, runtime: ProgramRuntime, config: EngineeringConfig, completion: str) -> None:
        self._runtime, self._config = runtime, config
        selected = next(
            (choice for choice in config.completions if choice.name == completion), None
        )
        if selected is None:
            raise ValueError("Requested completion is not declared by this Program")
        self._completion = selected

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
                RequestVerification(subject=candidate, policy=self._completion.verification_policy),
                f"{prefix}-request",
            ),
        )
        if (
            view.state.plan.subject.fingerprint != candidate.fingerprint
            or view.state.plan.policy != self._completion.verification_policy
            or view.state.plan.requirements != self._completion.requirements
        ):
            raise ValueError("Verification identifies different work")
        plan = view.state.plan.plan_id
        checks: list[CheckRun] = []
        if view.outcome == VerificationOutcome.PENDING:
            for index, runner in enumerate(self._completion.runners):
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
                or view.state.plan.policy != self._completion.verification_policy
                or view.state.plan.requirements != self._completion.requirements
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
            for attempt in range(self._completion.max_repairs + 1):
                work = EngineeringWork(task=request.task, attempt=attempt, feedback=feedback)
                _, value = await calls.call(
                    self._completion.implementation if attempt == 0 else self._completion.repair,
                    work.model_dump(mode="json"),
                    key=f"attempt-{attempt}-work",
                )
                candidate = self._completion.validate_candidate(value)
                view, unresolved = await self._verification(candidate, attempt)
                review = None
                outcome = unresolved
                if outcome is None and view.outcome == VerificationOutcome.ACCEPTED:
                    review = validate_result(
                        HumanReviewResult,
                        await human_review(
                            AttemptRuntime(self._runtime, attempt),
                            EngineeringReviewSubject(
                                completion=self._completion.name,
                                candidate=candidate,
                                verification=view,
                            ).model_dump(mode="json"),
                            self._completion.review,
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
                if outcome is None and attempt == self._completion.max_repairs:
                    outcome = EngineeringOutcome.REPAIRS_EXHAUSTED
                if outcome is not None:
                    return EngineeringResult(
                        outcome=outcome,
                        completion=self._completion.name,
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
    request = validate_result(EngineeringInput, inputs)
    return (
        await EngineeringCoordinator(
            runtime, config, request.completion or config.default_completion
        ).run(request)
    ).model_dump(mode="json")


APPLICATION_PROGRAMS = (
    ApplicationRegistration(
        "engineering",
        "3",
        EngineeringConfig,
        engineering,
        input_model=EngineeringInput,
        result_model=EngineeringResult,
    ),
)
