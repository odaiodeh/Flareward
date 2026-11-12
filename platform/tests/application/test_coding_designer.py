"""A configured coding designer proposes typed work; it owns no approval or scheduling."""

import asyncio
import json
from unittest.mock import create_autospec

import pytest
from support.artifacts import inline_content
from support.operations import operation_bundle
from support.verification import VerificationClock

from lumora.elements.coding.contracts import CodingInput
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ProgramRuntime
from lumora.services.identity.domain import Identity
from lumora.services.reviews.domain.models import ReviewResponse
from lumora.services.workspaces.domain.files import ArtifactFile, InlineFile
from plugins.adlc.programs.design import DesignFeedback, DesignRevision
from plugins.adlc.programs.designer import (
    COORDINATORS,
    CodingDesigner,
    CodingDesignerConfig,
    CodingDesignWork,
    coding_designer,
)


@pytest.fixture
def designer(application):
    runtime = create_autospec(ProgramRuntime, instance=True)
    config = CodingDesignerConfig(
        coding=operation_bundle(application.elements),
        loader=operation_bundle(application.elements),
        execution=ExecutionSelection(profile="coding"),
        artifact_execution=ExecutionSelection(profile="storage"),
    )
    runtime.invoke_element.return_value = {
        "content": '{"plan":"Implement addition and test negative, positive and zero inputs"}',
        "workspace": "root/design/work",
    }
    work = CodingDesignWork(
        request={
            "task": {"prompt": "Implement addition", "context": "Keep the interface"},
            "acceptance_criteria": ["Returns the sum"],
        },
        attempt=0,
    )
    return CodingDesigner(runtime, config), runtime, config, work


async def test_proposal_uses_saved_operation_and_stages_verified_inputs_on_selected_placement(
    designer,
):
    service, runtime, config, work = designer
    content = inline_content(b"original source")
    source = ArtifactFile(
        artifact={"artifact_id": "a" * 64, **content.identity.model_dump()}, path="src/answer.py"
    )
    work = CodingDesignWork.model_validate(
        {
            **work.model_dump(mode="json"),
            "request": {
                **work.request.model_dump(mode="json"),
                "task": {
                    **work.request.task.model_dump(mode="json"),
                    "files": [source.model_dump()],
                },
            },
        }
    )
    outcome = runtime.invoke_element.return_value
    runtime.invoke_element.side_effect = [content.model_dump(mode="json"), outcome]
    result = await service.run(work)
    loaded, coded = runtime.invoke_element.await_args_list
    assert loaded.args == (config.loader, source.artifact.model_dump(mode="json"))
    assert loaded.kwargs["execution"] == config.artifact_execution
    assert coded.args[0] == config.coding and coded.kwargs["execution"] == config.execution
    request = CodingInput.model_validate(coded.args[1])
    assert request.files == (InlineFile(path=source.path, content=content),)
    assert "Do not implement" in request.prompt
    assert "Keep the interface" in request.context and "Returns the sum" in request.context
    assert result.plan.startswith("Implement addition")
    runtime.start_child.assert_not_awaited()
    runtime.receive.assert_not_awaited()


async def test_revisions_include_recorded_feedback_without_copying_file_bytes_into_prompt(designer):
    service, runtime, _, work = designer
    feedback = DesignFeedback(
        design=DesignRevision(
            number=1, request=work.request.model_dump(mode="json"), proposal={"plan": "First plan"}
        ),
        response=ReviewResponse(
            key="review",
            decision="reject",
            data={"feedback": "Add a failure case"},
            issued_by=Identity.user("reviewer"),
            recorded_at=VerificationClock()(),
        ),
    )
    await service.run(work.model_copy(update={"attempt": 1, "feedback": feedback}))
    context = runtime.invoke_element.await_args.args[1]["context"]
    value = json.loads(context.split("Feature design request:\n", 1)[1])
    assert value["attempt"] == 1 and value["feedback"]["design_revision"] == 1
    assert value["feedback"]["proposal"]["plan"] == "First plan"
    assert value["feedback"]["review"]["data"] == {"feedback": "Add a failure case"}


@pytest.mark.parametrize(
    "content", ["private answer", '{"plan":""}', '{"plan":"ok","approved":true}']
)
async def test_invalid_model_proposals_are_rejected_without_exposing_returned_content(
    designer, content
):
    service, runtime, _, work = designer
    runtime.invoke_element.return_value = {"content": content, "workspace": "root/work"}
    with pytest.raises(ValueError, match="invalid proposal") as caught:
        await service.run(work)
    assert content not in str(caught.value)


async def test_invalid_task_fails_before_invoking_the_agent(designer):
    _, runtime, config, work = designer
    value = work.model_dump(mode="json")
    value["request"]["task"] = {"description": "not a coding task"}
    with pytest.raises(ValueError, match="violates its contract"):
        await coding_designer(runtime, value, config)
    runtime.invoke_element.assert_not_awaited()


async def test_cancellation_propagates_without_producing_a_proposal(designer):
    service, runtime, _, work = designer
    runtime.invoke_element.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await service.run(work)


def test_registered_contract_exposes_typed_task_and_saved_configuration():
    registration = COORDINATORS[0]
    assert registration.input_model is CodingDesignWork
    schema = CodingDesignWork.model_json_schema()
    assert schema["$defs"]["CodingInput"]["required"] == ["prompt"]
