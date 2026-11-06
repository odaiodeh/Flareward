"""Declared backend calls share publication contracts with graph Program calls."""

import pytest
from mas.application.programs.authoring import ProgramIssueCode
from mas.application.programs.composition.programs import APPLICATION_PROGRAMS
from mas.application.programs.registry import ApplicationRegistration
from mas.application.programs.service import ProgramContractError
from mas.domain.programs.models import (
    ApplicationDefinition,
    LiteralBinding,
    PathBinding,
    ProgramBody,
    ProgramDefinition,
)
from support.programs import ComposedConfig, composed_program
from support.typed_programs import APPLICATION_PROGRAMS as TYPED_PROGRAMS
from support.typed_programs import TypedInput


@pytest.fixture(autouse=True)
def installed(application):
    for registration in (*APPLICATION_PROGRAMS, *TYPED_PROGRAMS):
        application.applications.register(registration)


@pytest.fixture
def child():
    return ProgramBody(
        implementation=ApplicationDefinition(implementation="typed_program", version="1")
    )


def control(application, child, kind, config, **values):
    return ProgramDefinition(
        program_id="control",
        name="Control",
        owner=application.owner,
        implementation=ApplicationDefinition(
            implementation=kind, version="1", children={"body": child}, config=config
        ),
        **values,
    )


@pytest.mark.parametrize("pinned", [False, True])
@pytest.mark.parametrize("problem", ["required", "scope", "pass_through"])
async def test_map_contracts_reject_invalid_mapping_and_allow_correction(
    application, child, pinned, problem
):
    if pinned:
        named = ProgramDefinition(
            program_id="child", name="Child", owner=application.owner, **child.model_dump()
        )
        saved = await application.programs.save(named, application.owner)
        child = (
            await application.programs.publish(
                "child", application.owner, expected_version=saved.version
            )
        ).reference
    inputs = {"label": LiteralBinding(value="mapped").model_dump(mode="json")}
    if problem == "scope":
        inputs["amountAlias"] = PathBinding(path=("private-unavailable",)).model_dump(mode="json")
    config = {} if problem == "pass_through" else {"inputs": inputs}
    root = control(application, child, "map", config)
    saved = await application.programs.save(root, application.owner)
    readiness = await application.programs.validate(
        "control", application.owner, expected_version=saved.version
    )
    assert not readiness.valid
    assert readiness.issues[0].code == ProgramIssueCode.BINDING
    assert readiness.issues[0].path[:3] == ("implementation", "children", "body")
    assert "private-unavailable" not in readiness.issues[0].message
    with pytest.raises(ProgramContractError) as refused:
        await application.programs.publish(
            "control", application.owner, expected_version=saved.version
        )
    assert refused.value.issue == readiness.issues[0]
    inputs["amountAlias"] = PathBinding(path=("item",)).model_dump(mode="json")
    corrected = root.model_copy(
        update={
            "implementation": root.implementation.model_copy(update={"config": {"inputs": inputs}})
        }
    )
    changed = await application.programs.save(
        corrected, application.owner, expected_version=saved.version
    )
    assert (
        await application.programs.validate(
            "control", application.owner, expected_version=changed.version
        )
    ).valid
    revision = await application.programs.publish(
        "control", application.owner, expected_version=changed.version
    )
    assert revision.definition.program_id == "control"


@pytest.mark.parametrize("problem", ["state", "until", "literal_predicate"])
async def test_repeat_checks_consumed_child_results_without_exposing_values(
    application, child, problem
):
    config = {
        "inputs": {
            "amountAlias": PathBinding(path=("state",)).model_dump(mode="json"),
            "label": LiteralBinding(value="repair").model_dump(mode="json"),
        },
        "state": PathBinding(path=("total",)).model_dump(mode="json"),
        "until": LiteralBinding(value=True).model_dump(mode="json"),
    }
    if problem == "literal_predicate":
        config["until"] = LiteralBinding(value="private-not-a-boolean").model_dump(mode="json")
    else:
        config[problem] = PathBinding(path=("missing",)).model_dump(mode="json")
    saved = await application.programs.save(
        control(application, child, "repeat", config), application.owner
    )
    readiness = await application.programs.validate(
        "control", application.owner, expected_version=saved.version
    )
    assert not readiness.valid and readiness.issues[0].code == ProgramIssueCode.BINDING
    assert readiness.issues[0].path[:3] == ("implementation", "children", "body")
    assert "private-not-a-boolean" not in readiness.model_dump_json()


async def test_choose_checks_every_branch_and_pass_through_against_declared_input(
    application, child
):
    root = control(
        application,
        child,
        "choose",
        {"branches": {"approved": "body"}},
        input_schema={
            "type": "object",
            "properties": {"choice": {"type": "string"}},
            "required": ["choice"],
            "additionalProperties": False,
        },
    )
    saved = await application.programs.save(root, application.owner)
    assert not (
        await application.programs.validate(
            "control", application.owner, expected_version=saved.version
        )
    ).valid
    valid_inputs = {
        "amountAlias": LiteralBinding(value=1).model_dump(mode="json"),
        "label": LiteralBinding(value="chosen").model_dump(mode="json"),
    }
    other = child.model_copy(
        update={
            "input_schema": {
                "type": "object",
                "properties": {"ticket": {}},
                "required": ["ticket"],
                "additionalProperties": False,
            }
        }
    )
    root = root.model_copy(
        update={
            "implementation": root.implementation.model_copy(
                update={
                    "children": {"body": child, "other": other},
                    "config": {
                        "branches": {"approved": "body", "rejected": "other"},
                        "inputs": valid_inputs,
                    },
                }
            )
        }
    )
    changed = await application.programs.save(
        root, application.owner, expected_version=saved.version
    )
    readiness = await application.programs.validate(
        "control", application.owner, expected_version=changed.version
    )
    assert not readiness.valid
    assert readiness.issues[0].path[:3] == ("implementation", "children", "other")


async def test_unknown_choose_input_keeps_runtime_validation_instead_of_guessing(
    application, child
):
    saved = await application.programs.save(
        control(application, child, "choose", {"branches": {"approved": "body"}}),
        application.owner,
    )
    assert (
        await application.programs.validate(
            "control", application.owner, expected_version=saved.version
        )
    ).valid


async def test_custom_backend_contract_uses_normalized_parent_input_schema(application, child):
    application.applications.register(
        ApplicationRegistration(
            "typed_coordinator", "1", ComposedConfig, composed_program, input_model=TypedInput
        )
    )
    root = ProgramDefinition(
        program_id="coordinator",
        name="Coordinator",
        owner=application.owner,
        input_schema=TypedInput.model_json_schema(),
        implementation=ApplicationDefinition(
            implementation="typed_coordinator",
            version="1",
            children={
                "greet": child.model_copy(
                    update={
                        "input_schema": TypedInput.model_json_schema(
                            mode="serialization", by_alias=False
                        )
                    }
                )
            },
        ),
    )
    saved = await application.programs.save(root, application.owner)
    assert (
        await application.programs.validate(
            "coordinator", application.owner, expected_version=saved.version
        )
    ).valid
