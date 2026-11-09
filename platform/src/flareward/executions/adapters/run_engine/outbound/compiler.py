"""Translate authorized immutable program revisions to existing runtime contracts."""

from typing import Literal

from pydantic import JsonValue, ValidationError
from runengine import GraphBuilder, JoinPolicy, UnknownLabelPolicy
from runengine.coordination.environment_models import BorrowedEnvironment, OwnedEnvironment
from runengine.coordination.models import RunRequest
from runengine.coordination.targets import EnvironmentTarget
from runengine.core.refs import FunctionRef
from runengine.invocation.config import ExecutorConfig
from runengine.programs.graph.models.execution import GraphCallArguments
from runengine.programs.graph.policies.exponential import ExponentialBackoffPolicy

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.adapters.run_engine.inbound.elements import (
    evaluate_condition,
    execute_element,
    execute_operation,
)
from flareward.executions.adapters.run_engine.inbound.programs import (
    execute_program,
    map_program_inputs,
    map_program_outputs,
)
from flareward.executions.adapters.run_engine.outbound.profiles import (
    profile_catalog,
    supports_retained_environment,
)
from flareward.executions.adapters.run_engine.shared.models import (
    ApplicationCall,
    ElementCall,
    ElementSpecifications,
    ProgramPayload,
    ProgramPlacement,
    WorkBudgetBinding,
)
from flareward.executions.adapters.run_engine.shared.state import engine_state_type
from flareward.executions.domain.budgets import WorkLimits
from flareward.executions.domain.context import ExecutionContext
from flareward.executions.domain.placement import (
    GraphPlacementPlan,
    InvocationPlacement,
    PlacementScope,
    PreparedChildPlacement,
    PreparedInvocationPlacement,
    PreparedProgramPlacement,
)
from flareward.executions.domain.preferences import ExecutionProfileCatalog, ExecutionSelection
from flareward.executions.placement import ProfileAccess
from flareward.executions.profile_access import ExecutionProfileAccess
from flareward.programs.domain.models import (
    BodyPath,
    ElementStep,
    GraphDefinition,
    OperationStep,
    ProgramBody,
    ProgramDefinition,
    ProgramRef,
    ProgramRevision,
)
from flareward.programs.graph_context import step_contexts
from flareward.programs.graph_elements import GraphElementSpec
from flareward.programs.graph_state import graph_state_type
from flareward.programs.registry import ApplicationRegistry
from flareward.programs.service import ProgramService
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.identity.domain import Identity


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
        work_limits: WorkLimits | None = None,
        work_admission: FunctionRef | None = None,
        profile_access: ProfileAccess | None = None,
    ) -> None:
        self._programs = programs
        self._elements = elements
        self._applications = applications
        self._profiles = {name: config.model_copy(deep=True) for name, config in profiles.items()}
        if default_profile not in self._profiles:
            raise ValueError("Default execution profile is not installed")
        self._access = (
            profile_access
            if profile_access is not None
            else ExecutionProfileAccess(profile_catalog(self._profiles, default_profile))
        )
        self._bundles = ElementBundleResolver(elements)
        self._receiver = receiver
        self._cancellation = cancellation
        if receiver is not None:
            receiver.validate_portable()
        if cancellation is not None:
            cancellation.validate_portable()
        if (work_limits is None) != (work_admission is None):
            raise ValueError("Work limits require a durable admission binding")
        self._work_budget = (
            WorkBudgetBinding(limits=work_limits, admission=work_admission)
            if work_limits is not None and work_admission is not None
            else None
        )
        if work_admission is not None:
            work_admission.validate_portable()

    def _profile_name(
        self, selection: ExecutionSelection, default: str | None, approved: ExecutionProfileCatalog
    ) -> str:
        name = selection.profile or default or approved.default_profile
        if name not in self._profiles:
            raise ValueError("Execution profile is not approved")
        if name not in approved.profiles:
            raise PermissionError("Execution profile is not permitted for this owner")
        return name

    def authorize_template(self, payload: ProgramPayload, caller: Identity) -> None:
        """Withdrawn or changed execution policy requires explicit source replacement."""
        approved = self._access.catalog(caller)
        current = {name: self._profiles[name].model_dump(mode="json") for name in approved.profiles}
        if payload.placement.profiles != current or payload.work_budget != self._work_budget:
            raise PermissionError("Frozen execution settings are no longer permitted")

    def _target(
        self, selection: ExecutionSelection, default: str | None, approved: ExecutionProfileCatalog
    ) -> EnvironmentTarget | ExecutorConfig:
        if selection.environment:
            return EnvironmentTarget(name=selection.environment)
        return self._profiles[self._profile_name(selection, default, approved)].model_copy(
            deep=True
        )

    def _owned_environment(
        self, profile: str, approved: ExecutionProfileCatalog
    ) -> OwnedEnvironment:
        name = self._profile_name(ExecutionSelection(profile=profile), None, approved)
        target = self._profiles[name].model_copy(deep=True)
        if not supports_retained_environment(target):
            raise ValueError("Selected profile does not support a shared run environment")
        return OwnedEnvironment(target=target)

    async def preview(self, definition: ProgramDefinition, caller: Identity) -> GraphPlacementPlan:
        definition = ProgramDefinition.model_validate_json(definition.model_dump_json())
        graph = definition.implementation
        if not isinstance(graph, GraphDefinition):
            raise ValueError("Blueprint placement preview requires element graph steps")
        graph.validate_executable()
        steps = tuple(
            step for step in graph.steps if isinstance(step, (ElementStep, OperationStep))
        )
        if len(steps) != len(graph.steps):
            raise ValueError("Blueprint placement preview requires element graph steps")
        self._programs.authorize(definition, caller)
        approved = self._access.catalog(caller)
        if not graph.inputs.keys() <= set(graph_state_type(graph).model_fields):
            raise ValueError("Graph input bindings target unknown state channels")
        step_contexts(graph, self._elements)
        for profile in graph.environments.values():
            self._owned_environment(profile, approved)

        def placement(
            uid: str,
            category: Literal[
                ResourceCategory.NODE, ResourceCategory.CONDITION, ResourceCategory.OPERATION
            ],
            selection: ExecutionSelection,
        ) -> InvocationPlacement:
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
                else self._profile_name(selection, definition.execution_profile, approved),
                environment=selection.environment,
                binding_scope=PlacementScope.RUN
                if selection.environment
                else PlacementScope.INVOCATION,
            )

        try:
            for step in steps:
                self._bundles.validate(step.element, graph.resources)
            for route in graph.conditions:
                self._bundles.validate(route.condition, graph.resources)
        except ValidationError:
            raise ValueError("Invalid graph construction configuration") from None

        return GraphPlacementPlan(
            default_profile=self._profile_name(
                ExecutionSelection(), definition.execution_profile, approved
            ),
            environments=dict(graph.environments),
            invocations=(
                *(
                    placement(
                        step.uid,
                        ResourceCategory.OPERATION
                        if isinstance(step, OperationStep)
                        else ResourceCategory.NODE,
                        step.execution,
                    )
                    for step in steps
                ),
                *(
                    placement(route.source, ResourceCategory.CONDITION, route.execution)
                    for route in graph.conditions
                ),
            ),
        )

    async def compile(
        self,
        revision: ProgramRevision,
        caller: Identity,
        context: ExecutionContext,
        *,
        ancestors: tuple[tuple[str, int, BodyPath], ...] = (),
        imported_environments: frozenset[str] = frozenset(),
        body_path: BodyPath = (),
        inherited_profile: str | None = None,
    ) -> RunRequest:
        revision = ProgramRevision.model_validate_json(revision.model_dump_json())
        definition = revision.definition
        self._programs.authorize(definition, caller)
        approved = self._access.catalog(caller)
        if not ancestors:
            await self._programs.validate_revision(revision, caller)
        address = (definition.program_id, revision.revision, body_path)
        if address in ancestors:
            raise ValueError("Recursive program composition is not supported")
        ancestors = (*ancestors, address)
        body = definition.body_at(body_path)
        execution_profile = (
            body.execution_profile if body.execution_profile is not None else inherited_profile
        )
        implementation = body.implementation
        specifications = ElementSpecifications.from_registry(self._elements)
        available_environments = set(implementation.environments) | imported_environments
        placement = ProgramPlacement(
            default_profile=self._profile_name(ExecutionSelection(), execution_profile, approved),
            profiles={
                name: self._profiles[name].model_dump(mode="json") for name in approved.profiles
            },
            environments=tuple(sorted(available_environments)),
            child_imports=implementation.child_environment_imports
            if not isinstance(implementation, GraphDefinition)
            else {},
        )
        graph_request: dict[str, JsonValue] | None = None
        application: ApplicationCall | None = None
        children: dict[str, dict[str, JsonValue]] = {}
        child_placements: dict[str, PreparedChildPlacement] = {}
        invocation_placements: list[PreparedInvocationPlacement] = []

        def record_invocation(
            uid: str,
            category: Literal[
                ResourceCategory.NODE, ResourceCategory.CONDITION, ResourceCategory.OPERATION
            ],
            selection: ExecutionSelection,
        ) -> None:
            environment = selection.environment
            profile = (
                implementation.environments.get(environment)
                if environment
                else self._profile_name(selection, execution_profile, approved)
            )
            invocation_placements.append(
                PreparedInvocationPlacement(
                    step_uid=uid, category=category, profile=profile, environment=environment
                )
            )

        def record_child(name: str, request: RunRequest, imports: dict[str, str]) -> None:
            summary = ProgramPayload.model_validate(request.input).placement.summary
            if summary is None:
                raise ValueError("Compiled child is missing placement summary")
            child_placements[name] = PreparedChildPlacement(
                environment_imports=imports, program=summary
            )

        environments: dict[str, OwnedEnvironment | BorrowedEnvironment] = {
            name: self._owned_environment(profile, approved)
            for name, profile in implementation.environments.items()
        }
        if isinstance(implementation, GraphDefinition):
            self._bundles.validate_snapshot(implementation.resources)
            state_type = engine_state_type(implementation)
            channels = set(state_type.model_fields)
            if not implementation.inputs.keys() <= channels:
                raise ValueError("Graph input bindings target unknown state channels")
            contexts = step_contexts(implementation, self._elements)
            builder = GraphBuilder(
                state_type,
                recursion_limit=implementation.recursion_limit,
                join_policy=JoinPolicy(implementation.join_policy.value),
                unknown_label_policy=UnknownLabelPolicy.ERROR,
            )
            for step in implementation.steps:
                policy = ExponentialBackoffPolicy(max_attempts=step.max_attempts)
                if isinstance(step, (ElementStep, OperationStep)):
                    if isinstance(step, OperationStep) and not step.outputs.keys() <= channels:
                        raise ValueError("Operation output bindings target unknown state channels")
                    bundle = self._bundles.resolve(step.element, implementation.resources)
                    call = ElementCall(
                        bundle=bundle,
                        specifications=specifications.for_bundle(bundle),
                        context=context,
                        key=step.uid,
                        step=contexts[step.uid] if isinstance(step, ElementStep) else None,
                        receiver=self._receiver,
                    )
                    runner = self._target(step.execution, execution_profile, approved)
                    if (
                        step.execution.environment
                        and step.execution.environment not in available_environments
                    ):
                        raise ValueError(f"Undeclared environment: {step.execution.environment}")
                    record_invocation(
                        step.uid,
                        ResourceCategory.OPERATION
                        if isinstance(step, OperationStep)
                        else ResourceCategory.NODE,
                        step.execution,
                    )
                    arguments: dict[str, JsonValue] = {"call": call.model_dump(mode="json")}
                    if isinstance(step, OperationStep):
                        arguments.update(
                            step.model_dump(mode="json", include={"inputs", "outputs"})
                        )
                    builder.add_node(
                        step.uid,
                        execute_operation if isinstance(step, OperationStep) else execute_element,
                        kwargs=arguments,
                        runner=runner,
                        retry_policy=policy,
                    )
                else:
                    if not step.outputs.keys() <= channels:
                        raise ValueError("Program output bindings target unknown state channels")
                    if not set(step.environment_imports.values()) <= available_environments:
                        raise ValueError("Program call imports an undeclared parent environment")
                    inline = isinstance(step.program, ProgramBody)
                    child = (
                        await self._programs.revision(step.program, caller)
                        if isinstance(step.program, ProgramRef)
                        else revision
                    )
                    request = await self.compile(
                        child,
                        caller,
                        context,
                        ancestors=ancestors,
                        imported_environments=frozenset(step.environment_imports),
                        body_path=(*body_path, step.uid) if inline else (),
                        inherited_profile=placement.default_profile if inline else None,
                    )
                    record_child(step.uid, request, step.environment_imports)
                    builder.add_program_node(
                        step.uid,
                        request,
                        input_mapping=map_program_inputs,
                        output_mapping=map_program_outputs,
                        input_arguments=GraphCallArguments(
                            kwargs={
                                "bindings": step.model_dump(mode="json", include={"inputs"})[
                                    "inputs"
                                ],
                            }
                        ),
                        output_arguments=GraphCallArguments(
                            kwargs={
                                "key": step.uid,
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
                for successor in targets:
                    builder.add_edge(source, successor)
            for route in implementation.conditions:
                if (
                    route.execution.environment
                    and route.execution.environment not in available_environments
                ):
                    raise ValueError(f"Undeclared environment: {route.execution.environment}")
                bundle = self._bundles.resolve(route.condition, implementation.resources)
                resource = next(
                    entry.resource for entry in bundle.entries if entry.resource.key == bundle.root
                )
                GraphElementSpec.require(
                    self._elements.get_spec(resource.key.category, resource.type_key)
                )
                call = ElementCall(
                    bundle=bundle,
                    specifications=specifications.for_bundle(bundle),
                    context=context,
                    key=route.source,
                    step=contexts[route.source],
                    receiver=self._receiver,
                )
                record_invocation(route.source, ResourceCategory.CONDITION, route.execution)
                builder.add_conditional_edge(
                    route.source,
                    evaluate_condition,
                    route.branches,
                    kwargs={"call": call.model_dump(mode="json")},
                    runner=self._target(route.execution, execution_profile, approved),
                )
            builder.set_entry(implementation.entry).set_exit(implementation.exit)
            graph_request = builder.compile().request(state_type()).model_dump(mode="json")
        else:
            registration = self._applications.get(
                implementation.implementation, implementation.version
            )
            configuration = registration.configuration(implementation)
            self._bundles.validate_embedded(configuration)
            application = ApplicationCall.from_registration(registration)
            for name, target in implementation.children.items():
                imports = implementation.child_environment_imports.get(name, {})
                if not set(imports.values()) <= available_environments:
                    raise ValueError("Child imports an undeclared parent environment")
                inline = isinstance(target, ProgramBody)
                child = (
                    await self._programs.revision(target, caller)
                    if isinstance(target, ProgramRef)
                    else revision
                )
                child_request = await self.compile(
                    child,
                    caller,
                    context,
                    ancestors=ancestors,
                    imported_environments=frozenset(imports),
                    body_path=(*body_path, name) if inline else (),
                    inherited_profile=placement.default_profile if inline else None,
                )
                record_child(name, child_request, imports)
                children[name] = child_request.model_dump(mode="json")
        placement = placement.model_copy(
            update={
                "summary": PreparedProgramPlacement(
                    program=revision.reference,
                    body_path=body_path,
                    default_profile=placement.default_profile,
                    environments=implementation.environments,
                    imported_environments=tuple(sorted(imported_environments)),
                    invocations=tuple(invocation_placements),
                    children=child_placements,
                    dynamic_invocations=application is not None,
                )
            }
        )
        payload = ProgramPayload(
            program=revision.reference,
            body_path=body_path,
            content_digest=revision.content_digest,
            input_schema=body.input_schema,
            output_schema=body.output_schema,
            context=context,
            graph_request=graph_request,
            graph_inputs=implementation.inputs
            if isinstance(implementation, GraphDefinition)
            else {},
            graph_outputs=implementation.outputs
            if isinstance(implementation, GraphDefinition)
            else {},
            configuration=implementation.config
            if not isinstance(implementation, GraphDefinition)
            else {},
            application=application,
            children=children,
            specifications=specifications,
            placement=placement,
            receiver=self._receiver,
            cancellation=self._cancellation,
            work_budget=self._work_budget,
        )
        return RunRequest.create(
            execute_program, input=payload.model_dump(mode="json"), environments=environments
        )
