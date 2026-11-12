"""Declared backend calls share publication contracts with graph Program calls."""

from dataclasses import replace

import pytest
from pydantic import ValidationError
from support.programs import ComposedConfig, composed_program
from support.typed_programs import COORDINATORS as TYPED_PROGRAMS
from support.typed_programs import TypedInput

from lumora.programs.authoring import ProgramIssueCode
from lumora.programs.composition.models import MapConfig
from lumora.programs.composition.programs import COORDINATORS
from lumora.programs.domain.bindings import LiteralBinding, PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    ProgramBody,
    ProgramDefinition,
)
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.programs.service import ProgramContractError


@pytest.fixture(autouse=True)
def installed(application):
    for registration in (*COORDINATORS, *TYPED_PROGRAMS):
        application.applications.register(registration)


@pytest.fixture
def child():
    return ProgramBody(
        implementation=CustomCoordinatorDefinition(implementation="typed_program", version="1")
    )


def control(application, child, kind, config, **values):
    return ProgramDefinition(
        program_id="control",
        name="Control",
        owner=application.owner,
        implementation=CustomCoordinatorDefinition(
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
        CoordinatorRegistration(
            "typed_coordinator",
            "1",
            ComposedConfig,
            CustomCoordinatorStrategy(composed_program),
            input_model=TypedInput,
        )
    )
    root = ProgramDefinition(
        program_id="coordinator",
        name="Coordinator",
        owner=application.owner,
        input_schema=TypedInput.model_json_schema(),
        implementation=CustomCoordinatorDefinition(
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


@pytest.fixture
async def mapped_revision(application, child):
    config = {
        "inputs": {
            "amountAlias": PathBinding(path=("item",)).model_dump(mode="json"),
            "label": LiteralBinding(value="mapped").model_dump(mode="json"),
        }
    }
    draft = await application.programs.save(
        control(application, child, "map", config), application.owner
    )
    return await application.programs.publish(
        "control", application.owner, expected_version=draft.version
    )


async def test_dependency_expectations_are_frozen_and_detached(application, mapped_revision):
    declaration = mapped_revision.interface.dependencies["body"]
    assert declaration.inputs["amountAlias"] == PathBinding(path=("item",))
    assert "item" in declaration.scope_schema["required"]
    declaration.scope_schema["properties"].clear()
    reloaded = await application.programs.revision(mapped_revision.reference, application.owner)
    assert "item" in reloaded.interface.dependencies["body"].scope_schema["properties"]


@pytest.mark.parametrize("change", ["inputs", "outputs", "scope_schema", "result_schema"])
async def test_dependency_expectation_drift_rejects_admission(
    application, mapped_revision, monkeypatch, change
):
    original = MapConfig.child_contracts
    changed = {
        "inputs": {"amountAlias": LiteralBinding(value=2), "label": LiteralBinding(value="mapped")},
        "outputs": {"value": PathBinding(path=())},
        "scope_schema": {"type": "array"},
        "result_schema": {"type": "array"},
    }

    def declarations(config):
        contracts = original(config)
        return {
            name: replace(contract, **{change: changed[change]})
            for name, contract in contracts.items()
        }

    monkeypatch.setattr(MapConfig, "child_contracts", declarations)
    with pytest.raises(ProgramContractError, match="published contract"):
        await application.programs.validate_revision(mapped_revision, application.owner)


@pytest.mark.parametrize("declarations", [None, {"body": {}}, {"": {}}])
async def test_invalid_installed_dependency_declarations_have_safe_diagnostics(
    application, mapped_revision, monkeypatch, declarations
):
    monkeypatch.setattr(MapConfig, "child_contracts", lambda self: declarations)
    draft = await application.programs.draft("control", application.owner)
    report = await application.programs.validate(
        "control", application.owner, expected_version=draft.version
    )
    assert not report.valid
    assert report.issues[0].code == ProgramIssueCode.CONFIGURATION


async def test_restored_dependency_declaration_requires_a_bound_target(mapped_revision):
    document = mapped_revision.model_dump(mode="json")
    document["interface"]["dependencies"]["unbound"] = document["interface"]["dependencies"]["body"]
    document["content_digest"] = ""
    with pytest.raises(ValidationError, match="interface"):
        type(mapped_revision).model_validate(document)
