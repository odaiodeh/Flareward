from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.plan_builder import PlanBuilder
from flareward.programs.templates.contracts import ResolvedBlueprint


class GraphService:
    """
    Service for building graph plans from blueprint specifications.

    This service focuses solely on graph plan creation and building.
    Follows SOLID principles:
    - Single Responsibility: Only manages graph plan creation
    - Open/Closed: Extensible through composition
    - Dependency Inversion: Depends on abstractions (ElementRegistry)
    """

    def __init__(self, element_registry: ElementRegistry):
        """
        Initialize the GraphService.

        Args:
            element_registry: Registry containing all available element specifications
        """
        self._element_registry = element_registry
        self._plan_builder = PlanBuilder(element_registry)

    def build_plan(self, blueprint_spec: ResolvedBlueprint) -> GraphPlan:
        """
        Build a graph plan from a blueprint specification.

        Args:
            blueprint_spec: The blueprint specification to build from

        Returns:
            GraphPlan: The constructed graph plan
        """
        return self._plan_builder.build(blueprint_spec)

    @property
    def plan_builder(self) -> PlanBuilder:
        """Access to the plan builder for advanced use cases."""
        return self._plan_builder
