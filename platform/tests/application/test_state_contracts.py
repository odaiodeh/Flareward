"""State mapping and writer policy use the same draft/publication pipeline."""

import pytest
from support.condition_scenarios import routing_graph
from support.conditions import ELEMENT_SPECIFICATIONS
from support.operations import operation_graph

from lumora.programs.authoring import ProgramIssueCode
from lumora.programs.domain.models import (
    GraphWritePolicy,
    LiteralBinding,
    PathBinding,
    ProgramDefinition,
)
from lumora.programs.service import ProgramContractError


@pytest.mark.parametrize(
    "problem",
    ["unknown_initial", "invalid_initial", "unknown_output", "invalid_output", "dynamic_type"],
)
async def test_state_mapping_errors_are_saveable_but_not_publishable(application, problem):
    graph = operation_graph()
    if problem in {"unknown_initial", "invalid_initial"}:
        graph = graph.model_copy(
            update={
                "inputs": {
                    "missing" if problem == "unknown_initial" else "user_prompt": LiteralBinding(
                        value={"private": "initial"}
                    ),
                }
            }
        )
    else:
        outputs = (
            {"missing": LiteralBinding(value="value")}
            if problem == "unknown_output"
            else {"values": LiteralBinding(value="private-output")}
            if problem == "invalid_output"
            else {"messages": PathBinding(path=("text",))}
        )
        graph = graph.model_copy(
            update={"steps": (graph.steps[0].model_copy(update={"outputs": outputs}),)}
        )
    root = ProgramDefinition(
        program_id="state", name="State", owner=application.owner, implementation=graph
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "state", application.owner, expected_version=saved.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert "private" not in report.model_dump_json()
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            "state", application.owner, expected_version=saved.version
        )


async def test_unordered_declared_writers_require_explicit_reducer_policy(application):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    graph = routing_graph("router_boolean", {"boolean_value": True})
    root = ProgramDefinition(
        program_id="writers",
        name="Writers",
        owner=application.owner,
        implementation=graph.model_copy(update={"write_policy": GraphWritePolicy.ORDERED}),
    )
    saved = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        "writers", application.owner, expected_version=saved.version
    )
    assert not report.valid and "ordering" in report.issues[0].message
    corrected = await application.programs.save(
        root.model_copy(update={"implementation": graph}),
        application.owner,
        expected_version=saved.version,
    )
    assert (
        await application.programs.validate(
            "writers", application.owner, expected_version=corrected.version
        )
    ).valid
