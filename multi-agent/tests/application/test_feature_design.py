"""Design review preserves exact versions, bounded feedback and authoritative decisions."""

import asyncio

import pytest
from mas.domain.reviews import ReviewDecision
from mas_plugins.engineering.design import (
    APPLICATION_PROGRAMS,
    DesignOutcome,
    DesignResult,
    FeatureDesignConfig,
    FeatureRequest,
    feature_design,
)
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS
from pydantic import ValidationError
from support.design_runtime import DesignRuntime
from support.feature_design import APPLICATION_PROGRAMS as DESIGNERS
from support.feature_design import design_definition
from support.scenarios import publish


@pytest.fixture
def design_case(application):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    definition = design_definition(application.elements)
    config = FeatureDesignConfig.model_validate(definition.config)
    config = config.model_copy(
        update={"review": config.review.model_copy(update={"max_checks": 2})}
    )
    request = FeatureRequest(
        task={"description": "Add an operation"}, acceptance_criteria=("Works",)
    )
    return config, request


@pytest.mark.parametrize(
    "decisions,outcome,attempts",
    [
        (["approve"], DesignOutcome.APPROVED, 1),
        (["reject", "approve"], DesignOutcome.APPROVED, 2),
        (["reject", "reject"], DesignOutcome.REVISIONS_EXHAUSTED, 2),
        (["pending"], DesignOutcome.REVIEW_UNRESOLVED, 1),
        (["expired"], DesignOutcome.REVIEW_CLOSED, 1),
    ],
)
async def test_exact_designs_and_recorded_feedback_control_bounded_revision(
    design_case, decisions, outcome, attempts
):
    config, request = design_case
    runtime = DesignRuntime(decisions)
    result = DesignResult.model_validate(
        await feature_design(runtime, request.model_dump(mode="json"), config)
    )
    assert result.outcome == outcome and result.design.number == attempts
    assert result.design.request == request and len(runtime.work) == attempts
    assert result.review.review.specification.subject == result.design.model_dump(mode="json")
    if attempts == 2:
        previous = runtime.work[1].feedback
        assert previous.design.number == 1 and previous.design.request == request
        assert previous.response.decision == ReviewDecision.REJECT
        assert previous.response.data == {"feedback": "Add an error case"}
        assert runtime.opened[0].review_id != runtime.opened[1].review_id
        assert (
            runtime.opened[0].specification.fingerprint
            != runtime.opened[1].specification.fingerprint
        )


async def test_result_cannot_relabel_pending_or_substitute_the_reviewed_design(design_case):
    config, request = design_case
    result = await feature_design(DesignRuntime([]), request.model_dump(mode="json"), config)
    with pytest.raises(ValidationError, match="recorded review"):
        DesignResult.model_validate({**result, "outcome": "approved"})
    result["design"]["proposal"]["plan"] = "Unreviewed replacement"
    with pytest.raises(ValidationError, match="exact reviewed revision"):
        DesignResult.model_validate(result)


async def test_cancellation_owns_the_active_designer_and_does_not_open_review(design_case):
    config, request = design_case
    runtime = DesignRuntime([])
    start = runtime.start_child

    async def cancelled(*args, **kwargs):
        child = await start(*args, **kwargs)
        child.result.side_effect = asyncio.CancelledError()
        return child

    runtime.start_child = cancelled
    with pytest.raises(asyncio.CancelledError):
        await feature_design(runtime, request.model_dump(mode="json"), config)
    runtime.child.cancel.assert_awaited_once()
    assert not runtime.opened


async def test_design_is_an_ordinary_published_program_with_declared_child_contracts(
    application, design_case
):
    for registration in (*APPLICATION_PROGRAMS, *DESIGNERS):
        application.applications.register(registration)
    revision = await publish(
        application,
        "feature",
        design_definition(application.elements),
        input_schema=FeatureRequest.model_json_schema(),
        output_schema=DesignResult.model_json_schema(),
    )
    assert revision.definition.implementation.implementation == "feature_design"


async def test_invalid_proposals_fail_before_a_review_is_opened(design_case):
    config, request = design_case
    runtime = DesignRuntime([])
    start = runtime.start_child

    async def invalid(*args, **kwargs):
        child = await start(*args, **kwargs)
        child.result.return_value = {"plan": "", "private": "must not leak"}
        return child

    runtime.start_child = invalid
    with pytest.raises(ValueError, match="violates its contract") as error:
        await feature_design(runtime, request.model_dump(mode="json"), config)
    assert "must not leak" not in str(error.value) and not runtime.opened
