"""Import resolved authoring data using existing plan metadata and resource factories."""

from typing import Protocol

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.blueprints.contracts import ResolvedBlueprint
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.core.secrets import authored_configuration
from mas.domain.element_bundles import ResourceDefinition, ResourceKey
from mas.graph.plan_builder import PlanBuilder
from mas.graph.state.graph_state import GraphState
from mas.programs.models import (
    ConditionalRoute,
    ElementStep,
    ExecutionSelection,
    GraphDefinition,
    PathBinding,
    ProgramDefinition,
)
from mas.programs.service import ProgramService


class BlueprintSource(Protocol):
    async def resolve(self, blueprint_id: str, caller: Identity) -> ResolvedBlueprint: ...


class BlueprintProgramService:
    """Snapshot an authorized authoring blueprint through normal program protection and save."""

    def __init__(
        self,
        source: BlueprintSource,
        importer: BlueprintProgramImporter,
        programs: ProgramService,
    ) -> None:
        self._source, self._importer, self._programs = source, importer, programs

    async def save(
        self,
        blueprint_id: str,
        program_id: str,
        caller: Identity,
        *,
        execution_profile: str | None = None,
    ) -> ProgramDefinition:
        blueprint = await self._source.resolve(blueprint_id, caller)
        definition = self._importer.convert(
            blueprint, program_id=program_id, owner=caller, execution_profile=execution_profile
        )
        return await self._programs.save(definition, caller)


class BlueprintProgramImporter:
    def __init__(self, elements: ElementRegistry) -> None:
        self._elements = elements

    def convert(
        self,
        blueprint: ResolvedBlueprint,
        *,
        program_id: str,
        owner: Identity,
        execution_profile: str | None = None,
    ) -> ProgramDefinition:
        plan = PlanBuilder(self._elements).build(blueprint)
        roots, leaves = plan.get_roots(), plan.get_leaves()
        if len(roots) != 1 or len(leaves) != 1:
            raise ValueError("A blueprint must have exactly one entry and one final step")
        resources = tuple(
            ResourceDefinition(
                key=ResourceKey(category=category, rid=resource.rid.ref),
                type_key=resource.type,
                name=resource.name,
                config=authored_configuration(resource.config),
                implementation_version=self._elements.get_spec(category, resource.type).version,
            )
            for category in ResourceCategory
            for resource in getattr(blueprint, category.value)
        )
        placement = {
            (category, resource.rid.ref): ExecutionSelection(profile=resource.execution.profile)
            for category in ResourceCategory.plan_categories()
            for resource in getattr(blueprint, category.value)
        }
        authored_steps = {step.uid: step for step in blueprint.plan}
        edges: dict[str, list[str]] = {}
        conditions = []
        for step in plan:
            for dependency in step.after:
                edges.setdefault(dependency, []).append(step.uid)
            if step.condition is not None:
                conditions.append(
                    ConditionalRoute(
                        source=step.uid,
                        condition=ResourceKey(
                            category=ResourceCategory.CONDITION,
                            rid=step.condition.rid,
                        ),
                        branches=step.branches,
                        execution=(
                            authored_steps[step.uid].condition_execution
                            if authored_steps[step.uid].condition_execution is not None
                            else placement[ResourceCategory.CONDITION, step.condition.rid]
                        ),
                    )
                )
        bindings = {name: PathBinding(path=(name,)) for name in GraphState.model_fields}
        input_schema = GraphState.model_json_schema()
        input_schema["required"] = list(GraphState.model_fields)
        return ProgramDefinition(
            program_id=program_id,
            name=blueprint.name,
            owner=owner,
            execution_profile=execution_profile
            if execution_profile is not None
            else blueprint.execution_profile,
            input_schema=input_schema,
            output_schema=GraphState.model_json_schema(),
            implementation=GraphDefinition(
                steps=tuple(
                    ElementStep(
                        uid=step.uid,
                        element=ResourceKey(category=ResourceCategory.NODE, rid=step.rid),
                        metadata=step.meta,
                        execution=(
                            authored_steps[step.uid].execution
                            if authored_steps[step.uid].execution is not None
                            else placement[ResourceCategory.NODE, step.rid]
                        ),
                    )
                    for step in plan
                ),
                resources=resources,
                environments=dict(blueprint.environments),
                edges={source: tuple(targets) for source, targets in edges.items()},
                conditions=tuple(conditions),
                entry=roots[0].uid,
                exit=leaves[0].uid,
                inputs=bindings,
                outputs=bindings,
            ),
        )
