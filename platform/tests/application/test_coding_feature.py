"""The feature Program gates Engineering on the exact approved design."""

import asyncio
import json
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from support.design_runtime import DesignRuntime
from support.engineering_programs import APPLICATION_PROGRAMS as CANDIDATE_PROGRAMS
from support.engineering_programs import engineering_configuration
from support.engineering_runtime import ServiceRuntime
from support.feature_design import APPLICATION_PROGRAMS as DESIGNERS
from support.feature_design import design_definition
from support.operations import operation_resources
from support.scenarios import publish

from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    LiteralBinding,
    OperationStep,
    ProgramBody,
)
from flareward.programs.ports import ChildExecution, ProgramRuntime
from flareward.services.reviews.domain.models import ReviewDecision
from flareward.services.verification.domain.models import CheckVerdict
from plugins.adlc.programs.design import (
    APPLICATION_PROGRAMS as DESIGN_PROGRAMS,
)
from plugins.adlc.programs.design import (
    DesignResult,
    FeatureDesignConfig,
    FeatureRequest,
    feature_design,
)
from plugins.adlc.programs.feature import (
    APPLICATION_PROGRAMS as FEATURE_PROGRAMS,
)
from plugins.adlc.programs.feature import (
    CodingFeatureConfig,
    CodingFeatureInput,
    CodingFeatureResult,
    coding_feature,
)
from plugins.adlc.programs.program import APPLICATION_PROGRAMS as ENGINEERING_PROGRAMS
from plugins.adlc.programs.program import EngineeringInput, EngineeringResult, engineering
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS as CHECKS


class FeatureRuntime:
    """Own child handles while delegating actual behavior to application services."""

    execution_id = "root"

    def __init__(self, design_config, engineering_config, decisions, verdicts):
        self.design_config, self.engineering_config = design_config, engineering_config
        self.design = DesignRuntime(decisions)
        self.engineering = ServiceRuntime(verdicts, [ReviewDecision.APPROVE])
        self.calls = []
        self.child = None

    async def start_child(self, name, inputs, *, key, environment_imports=None):
        self.calls.append((name, inputs))
        child = create_autospec(ChildExecution, instance=True)
        child.execution_id = name

        async def result():
            if name == "design":
                return await feature_design(self.design, inputs, self.design_config)
            return await engineering(self.engineering, inputs, self.engineering_config)

        child.result.side_effect = result
        self.child = child
        return child


@pytest.fixture
def feature_case(application):
    for spec in (*REVIEWS, *CHECKS):
        application.elements.register_spec_class(spec)
    design = FeatureDesignConfig.model_validate(design_definition(application.elements).config)
    design = design.model_copy(
        update={"review": design.review.model_copy(update={"max_checks": 2})}
    )
    request = CodingFeatureInput(
        prompt="Implement an addition function",
        context="Preserve the API",
        acceptance_criteria=("Handles negative inputs",),
    )
    return design, engineering_configuration(application.elements), request


@pytest.mark.parametrize(
    "decisions,verdicts,outcome",
    [
        (["reject", "approve"], [CheckVerdict.PASSED], "verified"),
        (["approve"], [CheckVerdict.FAILED, CheckVerdict.PASSED], "verified"),
        (["approve"], [CheckVerdict.FAILED, CheckVerdict.FAILED], "engineering_unsatisfied"),
        (["reject", "reject"], [], "design_unsatisfied"),
        (["pending"], [], "design_unsatisfied"),
        (["expired"], [], "design_unsatisfied"),
    ],
)
async def test_only_approved_design_starts_engineering_with_exact_plan_and_criteria(
    feature_case, decisions, verdicts, outcome
):
    design, checks, request = feature_case
    runtime = FeatureRuntime(design, checks, decisions, verdicts)
    result = CodingFeatureResult.model_validate(
        await coding_feature(runtime, request.model_dump(mode="json"), CodingFeatureConfig())
    )
    assert result.outcome == outcome
    if outcome == "design_unsatisfied":
        assert [name for name, _ in runtime.calls] == ["design"]
        assert not runtime.engineering.work and result.engineering is None
    else:
        assert [name for name, _ in runtime.calls] == ["design", "engineering"]
        task = runtime.calls[1][1]["task"]
        assert task["prompt"] == request.prompt and task["context"].startswith(request.context)
        approved = json.loads(task["context"].split("Approved feature design:\n", 1)[1])
        assert approved["proposal"] == result.design.design.proposal.model_dump(mode="json")
        assert approved["acceptance_criteria"] == list(request.acceptance_criteria)
        assert approved["approval_id"] == result.design.review.review.review_id
        assert all(work[1]["task"] == task for work in runtime.engineering.work)
    if result.engineering is not None and result.engineering.outcome == "verified":
        with pytest.raises(ValidationError, match="accepted checks and human approval"):
            EngineeringResult.model_validate({**result.engineering.model_dump(), "review": None})


async def test_an_approved_different_request_cannot_start_engineering(feature_case):
    design, checks, request = feature_case
    runtime = FeatureRuntime(design, checks, ["approve"], [CheckVerdict.PASSED])
    foreign = request.model_copy(update={"prompt": "A different feature"})
    approved = await coding_feature(runtime, foreign.model_dump(mode="json"), CodingFeatureConfig())
    root = create_autospec(ProgramRuntime, instance=True)
    child = create_autospec(ChildExecution, instance=True)
    child.result.return_value = approved["design"]
    root.start_child.return_value = child
    with pytest.raises(ValueError, match="different feature request"):
        await coding_feature(root, request.model_dump(mode="json"), CodingFeatureConfig())
    root.start_child.assert_awaited_once()


@pytest.mark.parametrize("selection", [None, "default", "alternative"])
async def test_feature_preserves_completion_selection_without_changing_task_contract(
    feature_case, selection
):
    design, checks, request = feature_case
    checks = checks.model_copy(
        update={
            "completions": (
                *checks.completions,
                checks.completions[0].model_copy(update={"name": "alternative"}),
            )
        }
    )
    request = request.model_copy(update={"completion": selection})
    runtime = FeatureRuntime(design, checks, ["approve"], [CheckVerdict.PASSED])
    result = CodingFeatureResult.model_validate(
        await coding_feature(runtime, request.model_dump(mode="json"), CodingFeatureConfig())
    )
    assert result.engineering.completion == (selection or "default")
    assert runtime.calls[1][1]["completion"] == selection
    assert "completion" not in runtime.calls[0][1]["task"]
    assert "completion" not in runtime.calls[1][1]["task"]


async def test_feature_cannot_accept_a_different_engineering_completion(feature_case):
    design, checks, request = feature_case
    runtime = FeatureRuntime(design, checks, ["approve"], [CheckVerdict.PASSED])
    previous = await coding_feature(runtime, request.model_dump(mode="json"), CodingFeatureConfig())
    root = create_autospec(ProgramRuntime, instance=True)
    children = [create_autospec(ChildExecution, instance=True) for _ in range(2)]
    children[0].result.return_value = previous["design"]
    children[1].result.return_value = previous["engineering"]
    root.start_child.side_effect = children
    request = request.model_copy(update={"completion": "other"})
    with pytest.raises(ValueError, match="different completion choice"):
        await coding_feature(root, request.model_dump(mode="json"), CodingFeatureConfig())


async def test_cancellation_of_design_prevents_engineering_and_cancels_child(feature_case):
    _, _, request = feature_case
    root = create_autospec(ProgramRuntime, instance=True)
    child = create_autospec(ChildExecution, instance=True)
    child.result.side_effect = asyncio.CancelledError()
    root.start_child.return_value = child
    with pytest.raises(asyncio.CancelledError):
        await coding_feature(root, request.model_dump(mode="json"), CodingFeatureConfig())
    child.cancel.assert_awaited_once()
    root.start_child.assert_awaited_once()


def test_phase_aliases_cannot_overwrite_one_another():
    with pytest.raises(ValidationError, match="distinct child aliases"):
        CodingFeatureConfig(design="same", engineering="same")


@pytest.mark.parametrize("kind", ["backend", "graph"])
async def test_feature_publication_checks_consumed_results_without_requiring_optional_fields(
    application, feature_case, kind
):
    _, config, _ = feature_case
    for registration in (
        *DESIGN_PROGRAMS,
        *FEATURE_PROGRAMS,
        *ENGINEERING_PROGRAMS,
        *CANDIDATE_PROGRAMS,
        *DESIGNERS,
    ):
        application.applications.register(registration)
    candidate = ProgramBody(
        implementation=ApplicationDefinition(implementation="engineering_candidate", version="1")
    )
    engineering_body = ProgramBody(
        implementation=ApplicationDefinition(
            implementation="engineering",
            version="3",
            config=config.model_dump(mode="json"),
            children={"implementation": candidate, "repair": candidate},
        ),
        input_schema=EngineeringInput.model_json_schema(),
        output_schema=EngineeringResult.model_json_schema(),
    )
    if kind == "graph":
        result = await engineering(
            ServiceRuntime([CheckVerdict.FAILED, CheckVerdict.FAILED], []),
            {"task": "implement"},
            config,
        )
        result.pop("review")
        schema = EngineeringResult.model_json_schema()
        schema["properties"].pop("review")
        resources = operation_resources()
        engineering_body = ProgramBody(
            implementation=GraphDefinition(
                resources=resources,
                steps=(
                    OperationStep(
                        uid="work",
                        element=resources[0].key,
                        inputs={"text": LiteralBinding(value="noop")},
                    ),
                ),
                entry="work",
                exit="work",
                outputs=LiteralBinding(value=result),
            ),
            input_schema=EngineeringInput.model_json_schema(),
            output_schema=schema,
        )
    revision = await publish(
        application,
        "feature",
        ApplicationDefinition(
            implementation="coding_feature",
            version="1",
            children={
                "design": ProgramBody(
                    implementation=design_definition(application.elements),
                    input_schema=FeatureRequest.model_json_schema(),
                    output_schema=DesignResult.model_json_schema(),
                ),
                "engineering": engineering_body,
            },
        ),
        input_schema=CodingFeatureInput.model_json_schema(),
        output_schema=CodingFeatureResult.model_json_schema(),
    )
    assert revision.definition.implementation.implementation == "coding_feature"
