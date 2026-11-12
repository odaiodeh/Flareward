"""Installed Program models are enforced independently of execution infrastructure."""

from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from support.typed_programs import COORDINATORS, TypedConfig

from lumora.executions.models import StartExecution
from lumora.programs.authoring import ProgramIssueCode
from lumora.programs.domain.bindings import LiteralBinding, PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ProgramDefinition,
    ProgramRef,
)
from lumora.programs.invocation import CoordinatorInvoker, ProgramInvocationContractError
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.programs.signatures import ProgramInterfaces

PROGRAMS = {registration.key: registration for registration in COORDINATORS}


@pytest.fixture
def runtime():
    return create_autospec(ProgramRuntime, instance=True)


async def test_installed_models_normalize_aliases_defaults_and_serialized_results(runtime):
    registration = PROGRAMS["typed_program"]
    output = await CoordinatorInvoker(
        registration, ProgramInterfaces.capture(registration, {}, {})
    ).invoke(runtime, {"amountAlias": "3", "label": "valid"}, {})
    assert output == {"total": 6, "label": "valid", "tags": [], "summary": "valid:6"}
    runtime.sleep.assert_awaited_once_with(0.001)
    descriptor = registration.descriptor()
    assert "label" in descriptor.output_schema["properties"]
    assert "wireLabel" not in descriptor.output_schema["properties"]
    assert "summary" in descriptor.output_schema["required"]


@pytest.mark.parametrize(
    "inputs,configuration",
    [
        ({"amountAlias": "private-input", "label": "valid"}, {}),
        ({"amountAlias": 3, "label": "private-validator-input"}, {}),
        ({"amountAlias": 3, "label": "valid"}, {"multiplier": 0}),
    ],
)
async def test_input_and_configuration_failures_prevent_program_effects(
    runtime, inputs, configuration
):
    with pytest.raises(ProgramInvocationContractError) as raised:
        await CoordinatorInvoker(
            PROGRAMS["typed_program"], ProgramInterfaces.capture(PROGRAMS["typed_program"], {}, {})
        ).invoke(runtime, inputs, configuration)
    assert "private-input" not in str(raised.value) and "private-validator-input" not in str(
        raised.value
    )
    runtime.sleep.assert_not_awaited()


async def test_result_model_failure_is_safe_after_program_effects(runtime):
    with pytest.raises(ProgramInvocationContractError, match="output"):
        await CoordinatorInvoker(
            PROGRAMS["typed_program"], ProgramInterfaces.capture(PROGRAMS["typed_program"], {}, {})
        ).invoke(runtime, {"amount": 3, "label": "valid"}, {"invalid_result": True})
    runtime.sleep.assert_awaited_once_with(0.001)


@pytest.mark.parametrize("implementation", ["nonfinite_program", "model_error_program"])
async def test_nonfinite_output_and_internal_model_errors_are_contract_failures(
    runtime, implementation
):
    with pytest.raises(ProgramInvocationContractError) as raised:
        await CoordinatorInvoker(
            PROGRAMS[implementation], ProgramInterfaces.capture(PROGRAMS[implementation], {}, {})
        ).invoke(runtime, {}, {})
    assert "private-model-value" not in str(raised.value)


async def test_root_models_preserve_arrays_without_artificial_object_wrappers(runtime):
    assert await CoordinatorInvoker(
        PROGRAMS["numbers_program"], ProgramInterfaces.capture(PROGRAMS["numbers_program"], {}, {})
    ).invoke(runtime, ["1", 2], {}) == [
        2,
        4,
    ]


@pytest.mark.parametrize("value", [float("nan"), {"nested": [float("inf")]}])
def test_nonfinite_invocation_inputs_cannot_change_to_null_during_snapshotting(value):
    with pytest.raises(ValidationError):
        StartExecution(program=ProgramRef(program_id="typed", revision=1), inputs=value)


def test_installed_declaration_rejects_sync_entrypoints():
    def synchronous(runtime: ProgramRuntime, inputs, config):
        return inputs

    with pytest.raises(ValueError, match="async"):
        CoordinatorRegistration("sync", "1", TypedConfig, CustomCoordinatorStrategy(synchronous))


async def test_installed_serialized_result_contract_is_used_for_graph_binding_admission(
    application,
):
    application.applications.register(PROGRAMS["typed_program"])
    root = ProgramDefinition(
        program_id="result-port",
        name="Result port",
        owner=application.owner,
        implementation=GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="call",
                    program=ProgramBody(
                        implementation=CustomCoordinatorDefinition(
                            implementation="typed_program", version="1"
                        )
                    ),
                    inputs={
                        "amount": LiteralBinding(value=3),
                        "label": LiteralBinding(value="valid"),
                    },
                    outputs={"values": PathBinding(path=("wireLabel",))},
                ),
            ),
            entry="call",
            exit="call",
        ),
    )
    draft = await application.programs.save(root, application.owner)
    report = await application.programs.validate(
        root.program_id, application.owner, expected_version=draft.version
    )
    assert not report.valid and report.issues[0].code == ProgramIssueCode.BINDING
    assert report.issues[0].path == ("implementation", "steps", 0, "outputs", "values")
