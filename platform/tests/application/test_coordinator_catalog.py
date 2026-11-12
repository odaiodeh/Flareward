"""A catalog choice preserves one lifecycle while retaining typed coordinator semantics."""

from dataclasses import replace

import pytest
from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from support.typed_programs import COORDINATORS

from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ProgramKind,
    ProgramRef,
)
from lumora.programs.invocation import CoordinatorInvoker, ProgramInvocationContractError
from lumora.programs.registry import (
    CoordinatorRegistry,
    CustomCoordinatorStrategy,
    NativeGraphStrategy,
)
from lumora.programs.signatures import ProgramInterfaces


def test_catalog_contains_native_graph_and_plugin_without_constructing_capabilities():
    registry = CoordinatorRegistry()
    registration = COORDINATORS[0]
    registry.register(registration)
    descriptors = {item.key: item for item in registry.describe()}
    assert descriptors["graph"].kind == ProgramKind.GRAPH
    schema = Draft202012Validator(descriptors["graph"].configuration_schema)
    schema.validate({"steps": []})
    with pytest.raises(SchemaValidationError):
        schema.validate({"steps": ["invalid"]})
    assert descriptors[registration.key].kind == ProgramKind.APPLICATION
    native = registry.for_body(ProgramBody(implementation=GraphDefinition(steps=())))
    assert native.configuration(GraphDefinition(steps=())) == GraphDefinition(steps=())
    with pytest.raises(ValueError, match="already registered"):
        registry.register(native)


def test_native_graph_cannot_be_invoked_as_a_custom_coordinator():
    registry = CoordinatorRegistry()
    definition = CustomCoordinatorDefinition(implementation="graph", version="1")
    with pytest.raises(ValueError, match="does not match"):
        registry.for_body(ProgramBody(implementation=definition))
    with pytest.raises(ValueError, match="does not match"):
        registry.get("graph", "1").configuration(definition)
    native = registry.get("graph", "1")
    interface = ProgramInterfaces(registry).local(
        ProgramBody(implementation=GraphDefinition(steps=()))
    )
    with pytest.raises(ProgramInvocationContractError, match="custom coordinator strategy"):
        CoordinatorInvoker(native, interface)


@pytest.mark.parametrize("graph", [True, False])
def test_program_dependencies_preserve_targets_and_explicit_imports(graph):
    target = ProgramRef(program_id="review", revision=3)
    imports = {"workspace": "source"}
    implementation = (
        GraphDefinition(
            steps=(
                ProgramCallStep(
                    uid="reviewer",
                    program=target,
                    environment_imports=imports,
                ),
            )
        )
        if graph
        else CustomCoordinatorDefinition(
            implementation="engineering",
            version="4",
            children={"reviewer": target},
            child_environment_imports={"reviewer": imports},
        )
    )
    body = ProgramBody(implementation=implementation)
    dependency = body.dependencies["reviewer"]
    assert dependency.program == target
    assert dependency.environment_imports == imports
    changed = body.with_program_calls({"reviewer": ProgramRef(program_id="review", revision=4)})
    assert changed.dependencies["reviewer"].environment_imports == imports
    assert changed.program_calls["reviewer"].revision == 4
    assert body.program_calls["reviewer"].revision == 3


def test_interface_resolution_preserves_normalization_and_local_schema_references():
    registry = CoordinatorRegistry()
    registration = COORDINATORS[0]
    registry.register(registration)
    body = ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation=registration.key,
            version=registration.version,
        )
    )
    interfaces = ProgramInterfaces(registry)
    interface = interfaces.resolve(interfaces.snapshot(body))
    assert interface.inputs[0].document == body.input_schema
    assert interface.input_model is registration.input_model
    assert interface.outputs[0].document == body.output_schema
    if registration.result_model:
        assert interface.outputs[1].document == registration.result_model.model_json_schema(
            mode="serialization",
            by_alias=False,
        )


@pytest.mark.parametrize(
    "key,schema", [("other", GraphDefinition), ("graph", COORDINATORS[0].config_schema)]
)
def test_native_strategy_cannot_claim_a_custom_specification(key, schema):
    native = CoordinatorRegistry().get("graph", "1")
    with pytest.raises(ValueError, match="native graph specification"):
        replace(native, key=key, config_schema=schema)


def test_custom_strategy_cannot_claim_native_graph_identity():
    native = CoordinatorRegistry().get("graph", "1")
    with pytest.raises(ValueError, match="native graph strategy"):
        replace(native, strategy=COORDINATORS[0].strategy)


def test_catalog_strategy_and_kind_are_consistent():
    native = CoordinatorRegistry().get("graph", "1")
    custom = COORDINATORS[0]
    assert isinstance(native.strategy, NativeGraphStrategy)
    assert isinstance(custom.strategy, CustomCoordinatorStrategy)
    assert native.kind == ProgramKind.GRAPH
    assert custom.kind == ProgramKind.APPLICATION
    with pytest.raises(ValueError, match="explicit execution strategy"):
        replace(custom, strategy=None)
