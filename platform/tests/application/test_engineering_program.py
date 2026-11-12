"""Engineering coordinates real application services through the runtime port."""

import asyncio
from copy import deepcopy

import pytest
from pydantic import ValidationError
from support.check_runs import (
    MemoryCheckRunRepository,
    ScriptedCheckRunner,
    check_registration,
)
from support.engineering_programs import COORDINATORS as CANDIDATE_PROGRAMS
from support.engineering_programs import engineering_configuration
from support.engineering_runtime import CandidateExecution, ServiceRuntime
from support.operations import operation_bundle
from support.review_programs import review_body
from support.scenarios import publish

from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramBody
from lumora.services.identity.domain import Identity
from lumora.services.reviews.domain.models import ReviewDecision
from lumora.services.verification.check_service import CheckRunService
from lumora.services.verification.domain.models import CheckRequirement, CheckVerdict
from plugins.adlc.programs.program import (
    COORDINATORS,
    EngineeringCandidate,
    EngineeringConfig,
    EngineeringInput,
    EngineeringOutcome,
    EngineeringResult,
    EngineeringWork,
    engineering,
)
from plugins.adlc.programs.review import EngineeringReviewSubject
from plugins.human_review.elements.specification import (
    ELEMENT_SPECIFICATIONS as REVIEW_SPECS,
)
from plugins.human_review.programs.human_review import COORDINATORS as REVIEW_PROGRAMS
from plugins.verification.elements.specification import (
    ELEMENT_SPECIFICATIONS as VERIFICATION_SPECS,
)


@pytest.fixture
def configuration(application):
    for spec in (*REVIEW_SPECS, *VERIFICATION_SPECS):
        application.elements.register_spec_class(spec)
    return engineering_configuration(application.elements)


@pytest.mark.parametrize(
    "verdicts,decisions,expected,attempts",
    [
        ([CheckVerdict.PASSED], [ReviewDecision.APPROVE], EngineeringOutcome.VERIFIED, 1),
        (
            [CheckVerdict.FAILED, CheckVerdict.PASSED],
            [ReviewDecision.APPROVE],
            EngineeringOutcome.VERIFIED,
            2,
        ),
        (
            [CheckVerdict.PASSED, CheckVerdict.PASSED],
            [ReviewDecision.REJECT, ReviewDecision.APPROVE],
            EngineeringOutcome.VERIFIED,
            2,
        ),
        ([CheckVerdict.FAILED, CheckVerdict.FAILED], [], EngineeringOutcome.REPAIRS_EXHAUSTED, 2),
    ],
)
async def test_engineering_checks_exact_candidates_and_bounds_repairs(
    configuration, verdicts, decisions, expected, attempts
):
    runtime = ServiceRuntime(verdicts, decisions)
    result = await engineering(runtime, {"task": {"description": "implement"}}, configuration)
    assert result["outcome"] == expected and result["attempts"] == attempts
    assert result["candidate"]["identity"]["version"] == attempts - 1
    assert result["verification"]["state"]["plan"]["subject"] == result["candidate"]
    if attempts > 1:
        assert runtime.work[1][1]["feedback"]["candidate"]["identity"]["version"] == 0
        feedback = runtime.work[1][1]["feedback"]
        assert feedback["evidence"][0]["verdict"] == verdicts[0]
        if feedback["review"] is not None:
            assert feedback["review"]["decision"] == ReviewDecision.REJECT
            assert feedback["review"]["data"] == {"feedback": "checked"}
    if expected == EngineeringOutcome.VERIFIED:
        assert result["review"]["review"]["response"]["decision"] == "approve"
        subject = EngineeringReviewSubject.model_validate(
            result["review"]["review"]["specification"]["subject"]
        )
        assert subject.candidate.model_dump(mode="json") == result["candidate"]
        assert subject.verification.model_dump(mode="json") == result["verification"]


async def test_pending_review_captures_accepted_evidence_before_a_human_decides(configuration):
    runtime = ServiceRuntime([CheckVerdict.PASSED], [ReviewDecision.APPROVE])
    respond = runtime.receive

    async def inspect_before_response(name, *, timeout=None):
        record = await runtime.reviews.for_reviewer(
            name.removeprefix("lumora.review."), Identity.user("reviewer")
        )
        assert record.status == "pending" and record.response is None
        subject = EngineeringReviewSubject.model_validate(record.specification.subject)
        observed = await runtime.verification.inspect(
            subject.verification.state.plan.plan_id, runtime.actor
        )
        assert subject.verification == observed
        assert observed.state.evidence[0].subject_fingerprint == subject.candidate.fingerprint
        return await respond(name, timeout=timeout)

    runtime.receive = inspect_before_response
    result = await engineering(runtime, {"task": "implement"}, configuration)
    assert result["outcome"] == "verified"


@pytest.mark.parametrize("drift", ["missing-check", "different-verifier", "missing-report"])
async def test_verification_policy_cannot_weaken_published_requirements(configuration, drift):
    choice = configuration.completions[0]
    requirement = choice.requirements[0]
    requirements = choice.requirements
    if drift == "missing-check":
        requirements += (CheckRequirement(check="security@1", verifiers=frozenset({"scanner"})),)
    elif drift == "different-verifier":
        requirements = (requirement.model_copy(update={"verifiers": frozenset({"other-ci"})}),)
    else:
        requirements = (requirement.model_copy(update={"requires_reports": True}),)
    frozen = configuration.model_copy(
        update={"completions": (choice.model_copy(update={"requirements": requirements}),)}
    )
    runtime = ServiceRuntime([CheckVerdict.PASSED], [ReviewDecision.APPROVE])
    with pytest.raises(ValueError, match="different work"):
        await engineering(runtime, {"task": "implement"}, frozen)
    assert runtime.runner.submissions == 0 and len(runtime.work) == 1


@pytest.mark.parametrize(
    "changed",
    [
        "candidate",
        "plan",
        "receipt",
        "revision",
        "result",
        "completion",
        "scalar-type",
        "missing_evidence",
    ],
)
async def test_accepted_result_cannot_substitute_the_reviewed_candidate_or_evidence(
    configuration, changed
):
    result = await engineering(
        ServiceRuntime([CheckVerdict.PASSED], [ReviewDecision.APPROVE]),
        {"task": "implement"},
        configuration,
    )
    altered = deepcopy(result)
    subject = altered["review"]["review"]["specification"]["subject"]
    if changed == "candidate":
        subject["candidate"]["identity"]["version"] = "private-substitute"
    elif changed == "plan":
        subject["verification"]["state"]["plan"]["plan_id"] = "a" * 64
    elif changed == "receipt":
        subject["verification"]["state"]["evidence"][0]["run_id"] = "private-substitute"
    elif changed == "revision":
        subject["verification"]["state"]["revision"] += 1
    elif changed == "result":
        altered["verification"]["state"]["evidence"][0]["run_id"] = "private-substitute"
    elif changed == "completion":
        altered["completion"] = "private-substitute"
    elif changed == "scalar-type":
        subject["verification"]["state"]["revision"] = float(
            subject["verification"]["state"]["revision"]
        )
    else:
        subject.pop("verification")
    with pytest.raises(ValidationError, match="exact reviewed evidence") as failed:
        EngineeringResult.model_validate(altered)
    assert "private-substitute" not in str(failed.value)


async def test_rejected_checks_cannot_be_presented_as_an_acceptance_review(configuration):
    result = await engineering(
        ServiceRuntime([CheckVerdict.FAILED], []),
        {"task": "implement"},
        configuration.model_copy(
            update={
                "completions": (configuration.completions[0].model_copy(update={"max_repairs": 0}),)
            }
        ),
    )
    with pytest.raises(ValidationError, match="accepted verification"):
        EngineeringReviewSubject.model_validate(
            {
                "completion": result["completion"],
                "candidate": result["candidate"],
                "verification": result["verification"],
            }
        )


async def test_uncertain_check_does_not_start_repair_or_fake_acceptance(configuration):
    runtime = ServiceRuntime([], [])
    runner = ScriptedCheckRunner()
    runtime.runner = runner
    runtime.checks = CheckRunService(
        MemoryCheckRunRepository(),
        runtime.verification,
        {"ci@1": check_registration(runtime.owner, runner)},
        clock=runtime.clock,
    )
    result = await engineering(runtime, {"task": "implement"}, configuration)
    assert result["outcome"] == EngineeringOutcome.CHECK_UNRESOLVED
    assert result["verification"]["outcome"] == "pending"
    assert result["review"] is None and len(runtime.work) == 1
    assert runner.submissions == 1


async def test_mismatched_verification_candidate_cannot_be_accepted(configuration):
    runtime = ServiceRuntime([CheckVerdict.PASSED], [ReviewDecision.APPROVE])
    invoke = runtime.invoke_element

    async def substitute(bundle, inputs, *, key, execution=None):
        result = await invoke(bundle, inputs, key=key, execution=execution)
        if key.endswith("-request"):
            result["state"]["plan"]["subject"]["identity"]["version"] = 999
        return result

    runtime.invoke_element = substitute
    with pytest.raises(ValueError, match="different work"):
        await engineering(runtime, {"task": "implement"}, configuration)


async def test_review_timeout_cannot_become_approval_or_trigger_repair(configuration):
    runtime = ServiceRuntime([CheckVerdict.PASSED], [])

    async def no_response(name, *, timeout=None):
        raise TimeoutError()

    runtime.receive = no_response
    result = await engineering(runtime, {"task": "implement"}, configuration)
    assert result["outcome"] == EngineeringOutcome.REVIEW_CLOSED
    assert result["review"]["review"]["status"] == "cancelled"
    assert result["review"]["reason"] == "check_limit"
    assert len(runtime.work) == 1


async def test_cancellation_releases_the_active_child(configuration):
    runtime = ServiceRuntime([], [])
    child = CandidateExecution({"attempt": 0})
    child.cancelled = False

    async def cancelled_result():
        raise asyncio.CancelledError()

    async def cancel():
        child.cancelled = True

    async def start_child(name, inputs, *, key, environment_imports=None):
        return child

    child.result = cancelled_result
    child.cancel = cancel
    runtime.start_child = start_child
    with pytest.raises(asyncio.CancelledError):
        await engineering(runtime, {"task": "implement"}, configuration)
    assert child.cancelled


def test_arbitrary_operation_cannot_replace_verification_authority(configuration, application):
    with pytest.raises(ValidationError, match="registered scoped service"):
        EngineeringConfig.model_validate(
            {
                **configuration.model_dump(),
                "inspect_verification": operation_bundle(application.elements),
            }
        )


async def test_engineering_is_published_through_the_canonical_program_registry(
    configuration, application
):
    for registration in (*COORDINATORS, *CANDIDATE_PROGRAMS, *REVIEW_PROGRAMS):
        application.applications.register(registration)
    body = ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation="engineering_candidate", version="1"
        ),
        input_schema=EngineeringWork.model_json_schema(),
        output_schema=EngineeringCandidate.model_json_schema(),
    )
    definition = CustomCoordinatorDefinition(
        implementation="engineering",
        version="4",
        config=configuration.model_dump(mode="json"),
        children={
            "implementation": body,
            "repair": body,
            "reviewer": review_body(application.elements),
        },
    )
    revision = await publish(
        application,
        "engineering",
        definition,
        input_schema=EngineeringInput.model_json_schema(),
        output_schema=EngineeringResult.model_json_schema(),
    )
    assert revision.definition.implementation.implementation == "engineering"
