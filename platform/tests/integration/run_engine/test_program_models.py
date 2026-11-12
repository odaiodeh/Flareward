"""Installed Program contracts apply through the existing host and child execution path."""

import asyncio
from dataclasses import replace
from unittest.mock import create_autospec

import pytest
from runengine.coordination.models import RunRequest
from runengine.coordination.ports import CoordinationOperations
from runengine.invocation.errors import InvocationContractError
from support import typed_programs
from support.programs import ComposedConfig, composed_program
from support.scenarios import publish, run
from support.typed_programs import COORDINATORS, TypedInput, definition

from lumora.executions.adapters.run_engine.inbound.programs import execute_program
from lumora.executions.adapters.run_engine.shared.models import CoordinatorCall
from lumora.executions.domain.context import ExecutionContext
from lumora.executions.domain.models import ExecutionPhase
from lumora.executions.models import StartExecution
from lumora.programs.composition.models import MapConfig
from lumora.programs.composition.programs import COORDINATORS as CONTROLS
from lumora.programs.domain.bindings import LiteralBinding, PathBinding
from lumora.programs.domain.interfaces import ProgramSchemas
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
)
from lumora.programs.registry import (
    CoordinatorRegistration,
    CoordinatorRegistry,
    CustomCoordinatorStrategy,
)


@pytest.fixture(autouse=True)
def installed_models(application):
    for registration in COORDINATORS:
        application.applications.register(registration)


async def test_standalone_program_uses_installed_input_and_result_models(platform):
    revision = await publish(platform, "typed", definition(platform.owner).implementation)
    result = await run(platform, revision, {"amountAlias": "3", "label": "standalone"})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result == {
        "total": 6,
        "label": "standalone",
        "tags": [],
        "summary": "standalone:6",
    }
    # The execution record retains submitted intent, independently of normalization.
    assert result.inputs == {"amountAlias": "3", "label": "standalone"}


async def test_installed_backend_resolution_requires_no_coordinator_executor(platform, monkeypatch):
    revision = await publish(
        platform, "resolution", CustomCoordinatorDefinition(implementation="greeting", version="1")
    )
    context = ExecutionContext(
        identity=platform.owner,
        execution_id="resolution",
        root_execution_id="resolution",
        engine_handle="native",
    )
    prepared = await platform.gateway.prepare(
        revision, {"name": "native-resolution"}, context, "native"
    )
    request = RunRequest.model_validate_json(prepared.payload_json)
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.run_id = "native"

    def unavailable_executor(*args, **kwargs):
        raise NotImplementedError("Coordination does not provide a thread executor")

    with monkeypatch.context() as isolated:
        isolated.setattr(asyncio.get_running_loop(), "run_in_executor", unavailable_executor)
        result = await execute_program(operations, request.input)
    assert result == {"answer": "hello native-resolution"}


@pytest.mark.parametrize("owned", [True, False])
async def test_graph_calls_use_the_same_installed_models_for_owned_and_pinned_programs(
    platform, owned
):
    implementation = definition(platform.owner).implementation
    target = (
        ProgramBody(implementation=implementation)
        if owned
        else (await publish(platform, "typed", implementation)).reference
    )
    root = await publish(
        platform,
        "caller",
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="typed",
                    program=target,
                    inputs={
                        "amountAlias": PathBinding(path=("values", "amount")),
                        "label": PathBinding(path=("values", "label")),
                    },
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            entry="typed",
            exit="typed",
            inputs={"values": PathBinding(path=())},
            outputs={"summary": PathBinding(path=("values", "summary"))},
        ),
    )
    result = await run(platform, root, {"amount": "4", "label": "child"})
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result == {"summary": "child:8"}
    child = (await platform.executions.children(result.execution_id, platform.owner))[0]
    assert child.body_path == (("typed",) if owned else ())
    assert child.result == {"total": 8, "label": "child", "tags": [], "summary": "child:8"}


@pytest.mark.parametrize(
    "implementation,config,inputs,stage",
    [
        ("typed_program", {}, {"amount": 3, "label": "private-model-input"}, "input"),
        ("typed_program", {"invalid_result": True}, {"amount": 3, "label": "valid"}, "output"),
        ("model_error_program", {}, {}, "execution"),
        ("nonfinite_program", {}, {}, "output"),
    ],
)
async def test_installed_contract_failures_are_safe_native_execution_failures(
    platform, implementation, config, inputs, stage
):
    revision = await publish(
        platform,
        implementation,
        definition(platform.owner, implementation=implementation, config=config).implementation,
    )
    result = await run(platform, revision, inputs)
    assert result.phase == ExecutionPhase.FAILED
    assert result.failure.kind == "contract"
    assert f"Program {stage}" in result.failure.message
    assert "private-model-input" not in result.failure.message
    assert "private-model-value" not in result.failure.message


async def test_array_programs_run_standalone_and_through_backend_child_calls(platform):
    root = definition(platform.owner, implementation="numbers_program").model_copy(
        update={"input_schema": {"type": "array"}, "output_schema": {"type": "array"}}
    )
    draft = await platform.programs.save(root, platform.owner)
    revision = await platform.programs.publish(
        root.program_id, platform.owner, expected_version=draft.version
    )
    result = await run(platform, revision, ["1", 2])
    assert result.phase == ExecutionPhase.COMPLETED, result.failure
    assert result.result == [2, 4]
    caller = root.model_copy(
        update={
            "program_id": "array-caller",
            "implementation": CustomCoordinatorDefinition(
                implementation="composed", version="1", children={"greet": revision.reference}
            ),
        }
    )
    saved = await platform.programs.save(caller, platform.owner)
    published = await platform.programs.publish(
        caller.program_id, platform.owner, expected_version=saved.version
    )
    nested = await run(platform, published, ["1", 2])
    assert nested.result == result.result


@pytest.mark.parametrize("boundary", ["input", "output"])
async def test_published_json_contract_remains_authoritative_with_installed_models(
    platform, boundary
):
    root = definition(platform.owner)
    schema = (
        {"type": "object", "properties": {"amountAlias": {"type": "integer"}}}
        if boundary == "input"
        else {"type": "object", "properties": {"total": {"maximum": 3}}}
    )
    root = root.model_copy(update={f"{boundary}_schema": schema})
    draft = await platform.programs.save(root, platform.owner)
    revision = await platform.programs.publish(
        root.program_id, platform.owner, expected_version=draft.version
    )
    inputs = {"amountAlias": "3", "label": "valid"}
    if boundary == "input":
        with pytest.raises(ValueError, match="input violates"):
            await run(platform, revision, inputs, execution_id="refused-model-input")
        with pytest.raises(KeyError):
            await platform.records.get("refused-model-input")
    else:
        result = await run(platform, revision, inputs)
        assert result.phase == ExecutionPhase.FAILED
        assert result.failure.kind == "contract"
        assert "Program output violates its contract" in result.failure.message


@pytest.mark.parametrize("owned", [True, False])
@pytest.mark.parametrize("kind", ["map", "repeat", "choose"])
async def test_admitted_control_bindings_execute_normalized_owned_or_pinned_children(
    application, platform, owned, kind
):
    for registration in CONTROLS:
        application.applications.register(registration)
    implementation = definition(platform.owner).implementation
    target = (
        ProgramBody(implementation=implementation)
        if owned
        else (await publish(platform, "typed", implementation)).reference
    )
    source = {"map": "item", "repeat": "state", "choose": "amount"}[kind]
    config = {
        "inputs": {
            "amountAlias": PathBinding(path=(source,)).model_dump(mode="json"),
            "label": LiteralBinding(value="composed").model_dump(mode="json"),
        }
    }
    if kind == "repeat":
        config.update(
            {
                "state": PathBinding(path=("total",)).model_dump(mode="json"),
                "until": LiteralBinding(value=True).model_dump(mode="json"),
            }
        )
    elif kind == "choose":
        config["branches"] = {"approved": "body"}
    root = await publish(
        platform,
        "control",
        CustomCoordinatorDefinition(
            implementation=kind, version="1", config=config, children={"body": target}
        ),
    )
    inputs = {
        "map": {"items": [2, 3]},
        "repeat": {"state": 2},
        "choose": {"choice": "approved", "amount": 2},
    }[kind]
    execution = await run(platform, root, inputs)
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    children = await platform.executions.children(execution.execution_id, platform.owner)
    assert len(children) == (2 if kind == "map" else 1)
    assert all(child.result["summary"].startswith("composed:") for child in children)
    if kind == "map":
        assert [item["value"]["total"] for item in execution.result["items"]] == [4, 6]
    elif kind == "repeat":
        assert execution.result["reason"] == "satisfied"
        assert execution.result["state"] == 4 and execution.result["iterations"] == 1
    else:
        assert execution.result["value"]["total"] == 4


async def test_custom_coordinator_passes_normalized_input_through_declared_contract(
    application, platform
):
    application.applications.register(
        CoordinatorRegistration(
            "typed_coordinator",
            "1",
            ComposedConfig,
            CustomCoordinatorStrategy(composed_program),
            input_model=TypedInput,
        )
    )
    child = ProgramBody(
        implementation=definition(platform.owner).implementation,
        input_schema=TypedInput.model_json_schema(mode="serialization", by_alias=False),
    )
    revision = await publish(
        platform,
        "coordinator",
        CustomCoordinatorDefinition(
            implementation="typed_coordinator", version="1", children={"greet": child}
        ),
    )
    execution = await run(platform, revision, {"amountAlias": "3", "label": "normalized"})
    assert execution.phase == ExecutionPhase.COMPLETED, execution.failure
    assert execution.result["summary"] == "normalized:6"
    child_execution = (await platform.executions.children(execution.execution_id, platform.owner))[
        0
    ]
    assert child_execution.inputs == {"amount": 3, "label": "normalized", "tags": []}


async def test_worker_rejects_changed_model_after_successful_admission(platform, monkeypatch):
    revision = await publish(platform, "frozen", definition(platform.owner).implementation)
    context = ExecutionContext(
        identity=platform.owner,
        execution_id="frozen",
        root_execution_id="frozen",
        engine_handle="native",
    )
    prepared = await platform.gateway.prepare(
        revision, {"amountAlias": "3", "label": "valid"}, context, "native"
    )
    request = RunRequest.model_validate_json(prepared.payload_json)
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.run_id = "native"
    # Public function references resolve the module installed in the receiving worker.
    monkeypatch.setattr(typed_programs, "TypedInput", typed_programs.Numbers)
    with pytest.raises(InvocationContractError, match="published contract"):
        await execute_program(operations, request.input)
    assert not operations.mock_calls


async def test_configured_input_rejects_before_creating_an_execution(platform):
    revision = await publish(
        platform,
        "bounded",
        definition(platform.owner, implementation="bounded_echo").implementation,
    )
    with pytest.raises(ValueError, match="input violates"):
        await platform.executions.start(
            StartExecution(
                execution_id="not-admitted", program=revision.reference, inputs={"value": 6}
            ),
            platform.owner,
        )
    with pytest.raises(KeyError):
        await platform.executions.get("not-admitted", platform.owner)
    result = await run(platform, revision, {"value": 4})
    assert result.phase == ExecutionPhase.COMPLETED and result.result == {"value": 4}


async def test_configured_output_is_enforced_on_the_native_worker(platform):
    revision = await publish(
        platform,
        "bad-output",
        definition(
            platform.owner, implementation="bounded_echo", config={"output_limit": 2}
        ).implementation,
    )
    result = await run(platform, revision, {"value": 4})
    assert result.phase == ExecutionPhase.FAILED
    assert result.failure.kind == "contract" and "output violates" in result.failure.message


async def test_worker_rechecks_configured_contract_after_admission(platform, monkeypatch):
    revision = await publish(
        platform,
        "configured-drift",
        definition(platform.owner, implementation="bounded_echo").implementation,
    )
    context = ExecutionContext(
        identity=platform.owner,
        execution_id="configured-drift",
        root_execution_id="configured-drift",
        engine_handle="native",
    )
    prepared = await platform.gateway.prepare(revision, {"value": 2}, context, "native")
    request = RunRequest.model_validate_json(prepared.payload_json)
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.run_id = "native"
    monkeypatch.setattr(
        typed_programs.BoundedEchoConfig,
        "program_interface",
        lambda self: ProgramSchemas(input_schema={"type": "array"}),
    )
    with pytest.raises(InvocationContractError, match="configuration"):
        await execute_program(operations, request.input)
    assert not operations.mock_calls


async def test_worker_rechecks_dependency_expectations_before_effects(
    platform, application, monkeypatch
):
    for registration in CONTROLS:
        application.applications.register(registration)
    revision = await publish(
        platform,
        "dependency-drift",
        CustomCoordinatorDefinition(
            implementation="map",
            version="1",
            config={"inputs": {"name": LiteralBinding(value="mapped").model_dump(mode="json")}},
            children={
                "body": ProgramBody(
                    implementation=CustomCoordinatorDefinition(
                        implementation="greeting", version="1"
                    )
                )
            },
        ),
    )
    context = ExecutionContext(
        identity=platform.owner,
        execution_id="dependency-drift",
        root_execution_id="dependency-drift",
        engine_handle="native",
    )
    prepared = await platform.gateway.prepare(revision, {"items": [1]}, context, "native")
    request = RunRequest.model_validate_json(prepared.payload_json)
    original = MapConfig.child_contracts

    def declarations(config):
        return {
            name: replace(contract, result_schema={"type": "array"})
            for name, contract in original(config).items()
        }

    monkeypatch.setattr(MapConfig, "child_contracts", declarations)
    operations = create_autospec(CoordinationOperations, instance=True)
    operations.run_id = "native"
    with pytest.raises(InvocationContractError, match="configuration"):
        await execute_program(operations, request.input)
    assert not operations.mock_calls


def test_portable_custom_call_preserves_strategy_and_models():
    original = COORDINATORS[0]
    restored = CoordinatorCall.from_registration(original).resolve()
    assert restored == original
    assert restored.strategy.entrypoint is original.strategy.entrypoint


def test_native_graph_cannot_be_prepared_as_a_custom_call():
    with pytest.raises(ValueError, match="custom coordinator strategy"):
        CoordinatorCall.from_registration(CoordinatorRegistry().get("graph", "1"))
