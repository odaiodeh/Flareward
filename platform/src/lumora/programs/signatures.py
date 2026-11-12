"""Resolve invocation contracts without exposing coordinator mechanics to callers."""

from dataclasses import dataclass

from jsonschema import SchemaError
from pydantic import BaseModel, JsonValue

from lumora.programs.domain.interfaces import (
    CoordinatorIdentity,
    DependencyInterface,
    ProgramInterface,
    ProgramSchemas,
)
from lumora.programs.domain.models import ProgramBody
from lumora.programs.interfaces import InterfaceContract
from lumora.programs.ports import ConfiguredInterface
from lumora.programs.registry import CoordinatorRegistration, CoordinatorRegistry


@dataclass(frozen=True)
class InvocationInterface:
    """Raw intent schema, optional normalizer, and constraints on serialized results.

    Normalization is an explicit invocation stage. Its accepted inputs cannot be
    replaced by intersecting generated JSON schemas, which would lose coercion,
    aliases and custom validation semantics.
    """

    inputs: tuple[InterfaceContract, ...]
    input_model: type[BaseModel] | None
    outputs: tuple[InterfaceContract, ...]


class ProgramInterfaces:
    def __init__(self, coordinators: CoordinatorRegistry) -> None:
        self._coordinators = coordinators

    @staticmethod
    def capture(
        specification: CoordinatorRegistration,
        input_schema: dict[str, JsonValue],
        output_schema: dict[str, JsonValue],
        configuration: BaseModel | None = None,
    ) -> ProgramInterface:
        """Capture one coordinator boundary; owned bodies are resolved separately."""
        configured = (
            configuration.program_interface()
            if isinstance(configuration, ConfiguredInterface)
            else None
        )
        if isinstance(configuration, ConfiguredInterface) and not isinstance(
            configured, ProgramSchemas
        ):
            raise ValueError("Configured interfaces must return ProgramSchemas")
        declarations = specification.dependency_contracts(configuration)
        dependencies = {
            name: DependencyInterface(
                inputs=contract.inputs,
                scope_schema=contract.scope_schema,
                outputs=contract.outputs,
                result_model_schema=contract.result_model.model_json_schema(by_alias=False)
                if contract.result_model is not None
                else None,
                result_schema=contract.result_schema,
            )
            for name, contract in declarations.items()
        }
        interface = ProgramInterface(
            dependencies=dependencies,
            configured=configured,
            coordinator=CoordinatorIdentity(key=specification.key, version=specification.version),
            input_schema=input_schema,
            input_model_schema=specification.input_model.model_json_schema(mode="validation")
            if specification.input_model
            else None,
            normalized_input_schema=specification.input_model.model_json_schema(
                mode="serialization", by_alias=False
            )
            if specification.input_model
            else None,
            output_schema=output_schema,
            output_model_schema=specification.result_model.model_json_schema(mode="validation")
            if specification.result_model
            else None,
            normalized_output_schema=specification.result_model.model_json_schema(
                mode="serialization", by_alias=False
            )
            if specification.result_model
            else None,
        )
        for schema in (
            *interface.input_schemas,
            interface.input_model_schema,
            interface.normalized_input_schema,
            *interface.output_schemas,
            interface.output_model_schema,
            interface.normalized_output_schema,
        ):
            if schema is not None:
                InterfaceContract.check_schema(schema)
        for contract in dependencies.values():
            for schema in (contract.scope_schema, contract.result_model_schema, contract.result_schema):
                if schema is not None:
                    InterfaceContract.check_schema(schema)
        return interface.model_copy(deep=True)

    def local(self, body: ProgramBody) -> ProgramInterface:
        specification = self._coordinators.for_body(body)
        return self.capture(
            specification,
            body.input_schema,
            body.output_schema,
            specification.configuration(body.implementation),
        )

    def snapshot(self, body: ProgramBody) -> ProgramInterface:
        return self.local(body).model_copy(
            update={
                "children": {
                    name: self.snapshot(target)
                    for name, target in body.program_calls.items()
                    if isinstance(target, ProgramBody)
                }
            }
        )

    @classmethod
    def check_registration(
        cls,
        specification: CoordinatorRegistration,
        interface: ProgramInterface,
        configuration: BaseModel | None,
    ) -> None:
        try:
            installed = cls.capture(
                specification, interface.input_schema, interface.output_schema, configuration
            )
        except ValueError, TypeError, SchemaError:
            raise ValueError("Installed coordinator interface is invalid") from None
        if installed != interface.model_copy(update={"children": {}}):
            raise ValueError("Installed coordinator interface differs from the published contract")

    @classmethod
    def check_models(
        cls, specification: CoordinatorRegistration, interface: ProgramInterface
    ) -> None:
        cls.check_registration(
            specification, interface.model_copy(update={"configured": None, "dependencies": {}}), None
        )

    def resolve(self, interface: ProgramInterface) -> InvocationInterface:
        specification = self._coordinators.get(
            interface.coordinator.key, interface.coordinator.version
        )
        self.check_models(specification, interface)
        outputs = [InterfaceContract.root(schema) for schema in interface.output_schemas]
        if interface.normalized_output_schema is not None:
            outputs.append(InterfaceContract.root(interface.normalized_output_schema))
        return InvocationInterface(
            tuple(InterfaceContract.root(schema) for schema in interface.input_schemas),
            specification.input_model,
            tuple(outputs),
        )
