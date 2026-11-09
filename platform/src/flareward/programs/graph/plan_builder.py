from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.programs.domain.metadata import StepMeta
from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.models import ConditionMeta, Step
from flareward.programs.graph_elements import GraphElementSpec
from flareward.programs.templates.contracts import ResolvedBlueprint
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.construction import ResourceSpec, StepDef


class PlanBuilder:
    """
    Builds a logical GraphPlan from BlueprintSpec using ElementRegistry.
    No ElementInstances, no runtime objects - pure metadata extraction.
    """

    def __init__(self, registry: ElementRegistry) -> None:
        self._registry = registry

    def build(self, blueprint: ResolvedBlueprint) -> GraphPlan:
        """Build logical plan from blueprint specification."""
        plan = GraphPlan()

        for step_def in blueprint.plan:
            step = self._build_step(step_def, blueprint)
            plan.add_step(step)

        return plan

    def _build_step(self, step_def: StepDef, blueprint: ResolvedBlueprint) -> Step:
        """Build a single step from definition."""
        # Resolve node reference
        node_spec = self._find_node_by_ref(step_def.node.ref, blueprint)
        elem_spec = GraphElementSpec.require(
            self._registry.get_spec(ResourceCategory.NODE, node_spec.type)
        )
        step_meta = step_def.meta.model_copy(deep=True) if step_def.meta else StepMeta()
        step_meta.display_name = node_spec.name

        # Base step data
        step = Step(
            uid=step_def.uid,
            category=ResourceCategory.NODE,
            rid=node_spec.rid.ref,
            type_key=node_spec.type,
            reads=set(elem_spec.reads),
            writes=set(elem_spec.writes),
            after=self._normalize_after(step_def.after),
            meta=step_meta,
        )

        if step_def.branches and not step_def.exit_condition:
            raise ValueError("Graph branches require an exit condition")

        # Handle condition if present
        if step_def.exit_condition:
            condition_spec = self._find_condition_by_ref(step_def.exit_condition.ref, blueprint)
            condition_meta = self._build_condition_meta(condition_spec)

            step.condition = condition_meta
            step.branches = step_def.branches or {}

        return step

    def _build_condition_meta(self, condition_spec: ResourceSpec) -> ConditionMeta:
        """Extract condition metadata."""
        reads = self._extract_condition_reads(condition_spec)

        return ConditionMeta(rid=condition_spec.rid.ref, type_key=condition_spec.type, reads=reads)

    def _extract_condition_reads(self, condition_spec: ResourceSpec) -> set[str]:
        """Extract channels that a condition reads from its config."""
        elem_spec = GraphElementSpec.require(
            self._registry.get_spec(ResourceCategory.CONDITION, condition_spec.type)
        )
        return set(elem_spec.reads)

    def _find_node_by_ref(self, ref: str, blueprint: ResolvedBlueprint) -> ResourceSpec:
        """Find node by reference."""
        for node in blueprint.nodes:
            if node.rid.ref == ref:
                return node
        raise ValueError(f"Node reference '{ref}' not found")

    def _find_condition_by_ref(self, ref: str, blueprint: ResolvedBlueprint) -> ResourceSpec:
        """Find condition by reference."""
        for condition in blueprint.conditions:
            if condition.rid.ref == ref:
                return condition
        raise ValueError(f"Condition reference '{ref}' not found")

    @staticmethod
    def _normalize_after(after: str | list[str] | None) -> list[str]:
        """Normalize after dependencies to list."""
        if not after:
            return []
        return after if isinstance(after, list) else [after]
