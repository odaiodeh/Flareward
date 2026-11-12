"""Conservative interface checks: reject provable binding errors before dispatch."""

from collections.abc import Mapping

from jsonschema import SchemaError
from pydantic import AliasChoices, AliasPath, BaseModel

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.domain.bindings import LiteralBinding, Projection
from lumora.programs.domain.interfaces import ProgramInterface
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    OperationStep,
    ProgramBody,
    ProgramCallStep,
    ResultRoute,
)
from lumora.programs.graph_data import GraphDataScope
from lumora.programs.graph_flow import GraphFlow
from lumora.programs.graph_state import graph_state_type
from lumora.programs.interfaces import (
    BindingContractError,
    BindingSource,
    InterfaceContract,
    IssuePath,
)
from lumora.programs.registry import CoordinatorRegistry
from lumora.programs.signatures import InvocationInterface, ProgramInterfaces
from lumora.programs.state_contracts import StateContracts
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey


class BindingProjection:
    @staticmethod
    def _names(model: type[BaseModel]) -> dict[str, set[str]]:
        names: dict[str, set[str]] = {}
        for name, field in model.model_fields.items():
            names.setdefault(name, set()).add(name)
            alias = (
                field.validation_alias
                if model.model_config.get("validate_by_alias", True)
                else None
            )
            choices = alias.choices if isinstance(alias, AliasChoices) else [alias]
            for choice in choices:
                path = (
                    choice.path
                    if isinstance(choice, AliasPath)
                    else [choice]
                    if isinstance(choice, str)
                    else []
                )
                if path and isinstance(path[0], str):
                    key = path[0]
                    names.setdefault(key, set()).add(name)
        return names

    def validate_identity(
        self,
        source: InterfaceContract,
        *,
        target: InterfaceContract,
        model: type[BaseModel] | None = None,
    ) -> None:
        """Reject impossible pass-through fields; unknown/optional values stay dynamic."""
        source.check_overlap(target)
        for name in target.required():
            source.select((name,))
        for name in source.required():
            if target.member(name).schema is False:
                raise BindingContractError("Pass-through includes an undeclared input", (name,))
        if model is None or model.__pydantic_root_model__:
            return
        names = self._names(model)
        for name, field in model.model_fields.items():
            aliases = {key for key, fields in names.items() if name in fields}
            if field.is_required() and all(source.member(key).schema is False for key in aliases):
                raise BindingContractError("Required invocation input cannot be supplied", (name,))
        if model.model_config.get("extra") == "forbid" and source.required() - names.keys():
            raise BindingContractError("Pass-through includes an undeclared invocation input")

    def validate(
        self,
        bindings: Projection,
        *,
        source: BindingSource | None = None,
        target: InterfaceContract | None = None,
        model: type[BaseModel] | None = None,
    ) -> None:
        if not isinstance(bindings, dict):
            if isinstance(bindings, LiteralBinding):
                if target is not None:
                    target.validate_value(bindings.value)
                if model is not None:
                    try:
                        model.model_validate(bindings.value, by_name=True)
                    except ValueError, TypeError:
                        raise BindingContractError(
                            "Literal input violates the invocation contract"
                        ) from None
            elif source is not None:
                selected = source.select(bindings.path)
                self.validate_identity(
                    selected, target=target or InterfaceContract.root({}), model=model
                )
            return
        if model is not None and not model.__pydantic_root_model__:
            names = self._names(model)
            for name, field in model.model_fields.items():
                aliases = {key for key, fields in names.items() if name in fields}
                if field.is_required() and not aliases.intersection(bindings):
                    raise BindingContractError("Required invocation input has no binding", (name,))
            if model.model_config.get("extra") == "forbid" and bindings.keys() - names.keys():
                raise BindingContractError("Invocation binding targets an undeclared input")
        else:
            names = {}
        if target is not None and target.required() - bindings.keys():
            raise BindingContractError("Required destination fields have no bindings")
        if all(isinstance(binding, LiteralBinding) for binding in bindings.values()):
            values = {
                name: binding.value
                for name, binding in bindings.items()
                if isinstance(binding, LiteralBinding)
            }
            if target is not None:
                target.validate_value(values)
            if model is not None:
                try:
                    model.model_validate(values, by_name=True)
                except ValueError:
                    raise BindingContractError(
                        "Literal inputs violate the invocation contract"
                    ) from None
        for name, binding in bindings.items():
            destination = target.member(name) if target is not None else None
            try:
                if destination is not None and destination.schema is False:
                    raise BindingContractError("Binding targets an undeclared destination field")
                if isinstance(binding, LiteralBinding):
                    if destination is not None:
                        destination.validate_value(binding.value)
                elif source is not None:
                    selected = source.select(binding.path)
                    if destination is not None:
                        selected.check_overlap(destination)
            except BindingContractError as error:
                raise BindingContractError(str(error), (name, *error.path)) from None


class ProgramContracts:
    def __init__(self, elements: ElementRegistry, applications: CoordinatorRegistry) -> None:
        self._elements, self._applications = elements, applications
        self._interfaces = ProgramInterfaces(applications)
        self._projection = BindingProjection()
        self._state = StateContracts(elements)

    def validate(self, body: ProgramBody, children: Mapping[str, ProgramInterface]) -> None:
        try:
            local = self._interfaces.local(body)
        except ValueError, TypeError, SchemaError:
            raise BindingContractError(
                "Invalid configured Program interface", ("implementation", "config")
            ) from None
        for schemas in (local.input_schemas, local.output_schemas):
            for extra in schemas[1:]:
                InterfaceContract.root(schemas[0]).check_overlap(InterfaceContract.root(extra))
        graph = body.implementation
        if isinstance(graph, CustomCoordinatorDefinition):
            self._application(body, graph, children)
            return
        if graph.inputs.keys() & graph.READ_ONLY_CHANNELS:
            raise BindingContractError(
                "Graph input and result scopes are read-only", ("implementation", "inputs")
            )
        state = graph_state_type(graph)
        writable = InterfaceContract.root(state.writable_schema())
        self._check(
            graph.inputs,
            ("implementation", "inputs"),
            source=InterfaceContract.root(body.input_schema),
            target=writable,
        )
        resources = {resource.key: resource for resource in graph.resources}
        calls = {
            step.uid: self._interface(step, resources, children)
            for step in graph.steps
            if isinstance(step, (OperationStep, ProgramCallStep))
        }
        flow = GraphFlow(graph)
        self._state.validate(graph, flow)
        source = GraphDataScope(
            flow,
            InterfaceContract.root(body.input_schema),
            {uid: interface.outputs for uid, interface in calls.items()},
            InterfaceContract.root(state.model_json_schema(mode="serialization", by_alias=False)),
        )
        self._check(
            graph.outputs,
            ("implementation", "outputs"),
            source=source,
            target=InterfaceContract.root(body.output_schema),
        )
        for index, step in enumerate(graph.steps):
            if not isinstance(step, (OperationStep, ProgramCallStep)):
                continue
            interface = calls[step.uid]
            base = ("implementation", "steps", index)
            if step.outputs.keys() & graph.READ_ONLY_CHANNELS:
                raise BindingContractError(
                    "Graph input and result scopes are read-only", (*base, "outputs")
                )
            for target in interface.inputs or (None,):
                self._check(
                    step.inputs,
                    (*base, "inputs"),
                    source=source.at(step.uid),
                    target=target,
                    model=interface.input_model,
                )
            for output in interface.outputs:
                self._check(
                    step.outputs,
                    (*base, "outputs"),
                    source=output,
                    target=writable,
                )

        for index, route in enumerate(graph.conditions):
            if isinstance(route, ResultRoute):
                labels = list(route.branches)
                outcomes = [
                    {"type": "string", "enum": labels},
                    {"type": "array", "items": {"type": "string", "enum": labels}},
                ]
                booleans = [
                    value for value in (True, False) if str(value).lower() in route.branches
                ]
                if booleans:
                    outcomes.append({"type": "boolean", "enum": booleans})
                self._check(
                    route.selection,
                    ("implementation", "conditions", index, "selection"),
                    source=source.after(route.source),
                    target=InterfaceContract.root({"anyOf": outcomes}),
                )

    def _interface(
        self,
        step: OperationStep | ProgramCallStep,
        resources: Mapping[ResourceKey, ResourceDefinition],
        children: Mapping[str, ProgramInterface],
    ) -> InvocationInterface:
        if isinstance(step, OperationStep):
            resource = resources[step.element]
            spec = self._elements.get_spec(resource.key.category, resource.type_key)
            assert spec.input_schema is not None and spec.result_schema is not None
            return InvocationInterface(
                (),
                spec.input_schema,
                (
                    InterfaceContract.root(
                        spec.result_schema.model_json_schema(mode="serialization", by_alias=False)
                    ),
                ),
            )
        return self._interfaces.resolve(children[step.uid])

    def _application(
        self,
        body: ProgramBody,
        implementation: CustomCoordinatorDefinition,
        children: Mapping[str, ProgramInterface],
    ) -> None:
        registration = self._applications.get(implementation.implementation, implementation.version)
        configuration = registration.configuration(implementation)
        for name, contract in registration.dependency_contracts(configuration).items():
            if name not in children:
                raise BindingContractError(
                    "Required Program dependency is not bound",
                    ("implementation", "children", name),
                )
            child = children[name]
            interface = self._interfaces.resolve(child)
            input_model = interface.input_model
            schema = contract.scope_schema
            if schema is None:
                schema = (
                    registration.input_model.model_json_schema(mode="serialization", by_alias=False)
                    if registration.input_model is not None
                    else body.input_schema
                )
            path: IssuePath = ("implementation", "children", name)
            try:
                InterfaceContract.check_schema(schema)
            except SchemaError, BindingContractError:
                raise BindingContractError("Invalid declared child input scope", path) from None
            source = InterfaceContract.root(schema)
            for target in interface.inputs:
                if contract.inputs is None:
                    try:
                        self._projection.validate_identity(source, target=target, model=input_model)
                    except BindingContractError as error:
                        raise BindingContractError(str(error), (*path, *error.path)) from None
                else:
                    self._check(
                        contract.inputs, path, source=source, target=target, model=input_model
                    )
            output_target = (
                InterfaceContract.root(contract.result_model.model_json_schema(by_alias=False))
                if contract.result_model is not None
                else None
            )
            targets = [output_target]
            if contract.result_schema is not None:
                try:
                    InterfaceContract.check_schema(contract.result_schema)
                except SchemaError, BindingContractError:
                    raise BindingContractError(
                        "Invalid declared child result schema", path
                    ) from None
                targets.append(InterfaceContract.root(contract.result_schema))
            for output in interface.outputs:
                for result_target in targets:
                    self._check(
                        contract.outputs,
                        path,
                        source=output,
                        target=result_target,
                        model=contract.result_model,
                    )

    def _check(
        self,
        bindings: Projection,
        path: IssuePath,
        *,
        source: BindingSource | None = None,
        target: InterfaceContract | None = None,
        model: type[BaseModel] | None = None,
    ) -> None:
        try:
            self._projection.validate(bindings, source=source, target=target, model=model)
        except BindingContractError as error:
            raise BindingContractError(str(error), (*path, *error.path)) from None
