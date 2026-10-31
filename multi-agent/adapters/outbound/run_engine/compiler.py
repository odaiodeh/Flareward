"""Translate authorized immutable program revisions to existing runtime contracts."""

from inbound.run_engine.elements import evaluate_condition, execute_element
from inbound.run_engine.programs import execute_program, map_program_inputs, map_program_outputs
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.core.enums import ResourceCategory
from mas.core.execution_context import ExecutionContext
from mas.core.identity import Identity
from mas.domain.element_bundles import ElementBundle
from mas.execution.placement import GraphPlacementPlan, InvocationPlacement, PlacementScope
from mas.programs.graph_context import step_contexts
from mas.programs.models import (
    ElementStep,
    ExecutionSelection,
    GraphDefinition,
    ProgramDefinition,
    ProgramRevision,
)
from mas.programs.registry import ApplicationRegistry
from mas.programs.service import ProgramService
from pydantic import ValidationError
from run_engine.models import ElementCall, ProgramPayload
from run_engine.state import ProgramGraphState
from runengine import GraphBuilder, JoinPolicy, UnknownLabelPolicy
from runengine.coordination.environment_models import OwnedEnvironment
from runengine.coordination.models import RunRequest
from runengine.coordination.targets import EnvironmentTarget
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ExecutorConfig
from runengine.programs.graph.models.execution import GraphCallArguments
from runengine.programs.graph.policies.exponential import ExponentialBackoffPolicy

from outbound.run_engine.profiles import supports_retained_environment


class ProgramCompiler:
    def __init__(
        self,
        programs: ProgramService,
        elements: ElementRegistry,
        applications: ApplicationRegistry,
        profiles: dict[str, ExecutorConfig],
        default_profile: str,
        receiver: FunctionRef | None = None,
        cancellation: FunctionRef | None = None,
    ) -> None:
        self._programs = programs
        self._elements = elements
        self._applications = applications
        self._profiles = {name: config.model_copy(deep=True) for name, config in profiles.items()}
        if default_profile not in self._profiles:
            raise ValueError("Default execution profile is not installed")
        self._default = default_profile
        self._bundles = ElementBundleResolver(elements)
        self._receiver = receiver
        self._cancellation = cancellation
        if receiver is not None:
            receiver.validate_portable()
        if cancellation is not None:
            cancellation.validate_portable()

    def _profile_name(self, selection: ExecutionSelection, default: str | None) -> str:
        name = selection.profile or default or self._default
        if name not in self._profiles:
            raise ValueError(f"Execution profile is not approved: {name}")
        return name

    def _target(self, selection: ExecutionSelection, default: str | None):
        if selection.environment:
            return EnvironmentTarget(name=selection.environment)
        return self._profiles[self._profile_name(selection, default)].model_copy(deep=True)

    def _owned_environment(self, profile: str) -> OwnedEnvironment:
        target = self._target(ExecutionSelection(profile=profile), None)
        if not supports_retained_environment(target):
            raise ValueError("Selected profile does not support a shared run environment")
        return OwnedEnvironment(target=target)

    async def preview(self, definition: ProgramDefinition, caller: Identity) -> GraphPlacementPlan:
        definition = ProgramDefinition.model_validate_json(definition.model_dump_json())
        graph = definition.implementation
        if not isinstance(graph, GraphDefinition) or any(
            not isinstance(step, ElementStep) for step in graph.steps
        ):
            raise ValueError("Blueprint placement preview requires element graph steps")
        self._programs.authorize(definition, caller)
        if not graph.inputs.keys() <= set(ProgramGraphState.model_fields):
            raise ValueError("Graph input bindings target unknown state channels")
        step_contexts(graph, self._elements)
        for profile in graph.environments.values():
            self._owned_environment(profile)

        def placement(uid: str, category: ResourceCategory, selection: ExecutionSelection):
            if (
                selection.environment is not None
                and selection.environment not in graph.environments
            ):
                raise ValueError(f"Undeclared environment: {selection.environment}")
            return InvocationPlacement(
                step_uid=uid,
                category=category,
                profile=graph.environments[selection.environment]
                if selection.environment
                else self._profile_name(selection, definition.execution_profile),
                environment=selection.environment,
                binding_scope=PlacementScope.RUN
                if selection.environment
                else PlacementScope.INVOCATION,
            )

        try:
            for step in graph.steps:
                self._bundles.validate(step.element, graph.resources)
            for route in graph.conditions:
                self._bundles.validate(route.condition, graph.resources)
        except ValidationError:
            raise ValueError("Invalid graph construction configuration") from None

        return GraphPlacementPlan(
            default_profile=self._profile_name(ExecutionSelection(), definition.execution_profile),
            environments=dict(graph.environments),
            invocations=(
                *(
                    placement(step.uid, ResourceCategory.NODE, step.execution)
                    for step in graph.steps
                ),
                *(
                    placement(route.source, ResourceCategory.CONDITION, route.execution)
                    for route in graph.conditions
                ),
            ),
        )

    def _specifications(self, bundle: ElementBundle | None = None) -> tuple[FunctionRef, ...]:
        if bundle is not None:
            identities = {
                (entry.resource.key.category, entry.resource.type_key) for entry in bundle.entries
            }
            return tuple(
                FunctionRef.from_callable(self._elements.get_spec(category, type_key))
                for category, type_key in sorted(identities)
            )
        return tuple(
            FunctionRef.from_callable(spec)
            for specifications in self._elements.get_categories_map().values()
            for spec in specifications.values()
        )

    async def compile(
        self,
        revision: ProgramRevision,
        caller: Identity,
        context: ExecutionContext,
        *,
        ancestors: tuple[str, ...] = (),
        imported_environments: frozenset[str] = frozenset(),
    ) -> RunRequest:
        revision = ProgramRevision.model_validate_json(revision.model_dump_json())
        definition = revision.definition
        self._programs.authorize(definition, caller)
        if definition.program_id in ancestors:
            raise ValueError("Recursive program composition is not supported")
        ancestors = (*ancestors, definition.program_id)
        payload = ProgramPayload(
            revision=revision,
            context=context,
            receiver=self._receiver,
            cancellation=self._cancellation,
            specifications=self._specifications(),
            element_target=self._target(
                ExecutionSelection(), definition.execution_profile
            ).model_dump(mode="json"),
        )
        environments = {}
        implementation = definition.implementation
        if isinstance(implementation, GraphDefinition):
            channels = set(ProgramGraphState.model_fields)
            if not implementation.inputs.keys() <= channels:
                raise ValueError("Graph input bindings target unknown state channels")
            available_environments = set(implementation.environments) | imported_environments
            contexts = step_contexts(implementation, self._elements)
            builder = GraphBuilder(
                ProgramGraphState,
                recursion_limit=implementation.recursion_limit,
                join_policy=JoinPolicy.ACTIVE,
                unknown_label_policy=UnknownLabelPolicy.ERROR,
            )
            for step in implementation.steps:
                policy = ExponentialBackoffPolicy(max_attempts=step.max_attempts)
                if isinstance(step, ElementStep):
                    bundle = self._bundles.resolve(step.element, implementation.resources)
                    call = ElementCall(
                        bundle=bundle,
                        specifications=self._specifications(bundle),
                        context=context,
                        step=contexts[step.uid],
                        receiver=self._receiver,
                    )
                    target = self._target(step.execution, definition.execution_profile)
                    if (
                        step.execution.environment
                        and step.execution.environment not in available_environments
                    ):
                        raise ValueError(f"Undeclared environment: {step.execution.environment}")
                    builder.add_node(
                        step.uid,
                        execute_element,
                        kwargs={"call": call.model_dump(mode="json")},
                        runner=target,
                        retry_policy=policy,
                    )
                else:
                    if not step.outputs.keys() <= channels:
                        raise ValueError("Program output bindings target unknown state channels")
                    if not set(step.environment_imports.values()) <= available_environments:
                        raise ValueError("Program call imports an undeclared parent environment")
                    child = await self._programs.revision(step.program, caller)
                    request = await self.compile(
                        child,
                        caller,
                        context,
                        ancestors=ancestors,
                        imported_environments=frozenset(step.environment_imports),
                    )
                    builder.add_program_node(
                        step.uid,
                        request,
                        input_mapping=map_program_inputs,
                        output_mapping=map_program_outputs,
                        input_arguments=GraphCallArguments(
                            kwargs={
                                "bindings": {
                                    name: binding.model_dump(mode="json")
                                    for name, binding in step.inputs.items()
                                },
                            }
                        ),
                        output_arguments=GraphCallArguments(
                            kwargs={
                                "bindings": {
                                    name: binding.model_dump(mode="json")
                                    for name, binding in step.outputs.items()
                                },
                            }
                        ),
                        environment_imports=step.environment_imports,
                        retry_policy=policy,
                    )
            for source, targets in implementation.edges.items():
                for target in targets:
                    builder.add_edge(source, target)
            for route in implementation.conditions:
                if (
                    route.execution.environment
                    and route.execution.environment not in available_environments
                ):
                    raise ValueError(f"Undeclared environment: {route.execution.environment}")
                bundle = self._bundles.resolve(route.condition, implementation.resources)
                call = ElementCall(
                    bundle=bundle,
                    specifications=self._specifications(bundle),
                    context=context,
                    step=contexts[route.source],
                    receiver=self._receiver,
                )
                builder.add_conditional_edge(
                    route.source,
                    evaluate_condition,
                    route.branches,
                    kwargs={"call": call.model_dump(mode="json")},
                    runner=self._target(route.execution, definition.execution_profile),
                )
            builder.set_entry(implementation.entry).set_exit(implementation.exit)
            payload.graph_request = (
                builder.compile().request(ProgramGraphState()).model_dump(mode="json")
            )
            environments = {
                name: self._owned_environment(profile)
                for name, profile in implementation.environments.items()
            }
        else:
            registration = self._applications.get(
                implementation.implementation, implementation.version
            )
            registration.config_schema.model_validate(implementation.config, by_name=True)
            payload.application_function = FunctionRef.from_callable(registration.execute)
            payload.configuration_schema = FunctionRef.from_callable(registration.config_schema)
            for name, reference in implementation.children.items():
                child = await self._programs.revision(reference, caller)
                payload.children[name] = (
                    await self.compile(child, caller, context, ancestors=ancestors)
                ).model_dump(mode="json")
        return RunRequest.create(
            execute_program, input=payload.model_dump(mode="json"), environments=environments
        )
