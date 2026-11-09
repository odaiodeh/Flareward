"""Build full-graph element context from configuration, without constructing clients."""

from flareward.elements.catalog.card_service import ElementCardService
from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.configuration.meta import ElementConfigMeta
from flareward.elements.construction.references import references
from flareward.elements.domain.cards import ElementCard
from flareward.programs.domain.models import ElementStep, GraphDefinition, OperationStep, ProgramRef
from flareward.programs.graph.graph_plan import GraphPlan
from flareward.programs.graph.models.adjacency import AdjacentNodes
from flareward.programs.graph.models.step_context import StepContext
from flareward.programs.graph.models.workflow import Step
from flareward.programs.graph.topology.finalizer_analyzer import FinalizerAnalyzer
from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory


def step_contexts(graph: GraphDefinition, registry: ElementRegistry) -> dict[str, StepContext]:
    configurations = []
    for resource in graph.resources:
        schema = registry.get_schema(resource.key.category, resource.type_key)
        config = schema.model_validate(resource.config, by_name=True)
        configurations.append(
            ElementConfigMeta(
                rid=resource.key.rid,
                category=resource.key.category,
                type_key=resource.type_key,
                name=resource.name,
                config=config,
                dependency_rids=[key.rid for key in references(config)],
            )
        )
    resource_cards = ElementCardService(registry).build_all_cards(configurations)
    plan = GraphPlan()
    cards: dict[str, ElementCard] = {}
    conditions = {route.source: route for route in graph.conditions}
    for step in graph.steps:
        if isinstance(step, (ElementStep, OperationStep)):
            card = resource_cards[step.element.rid].model_copy(update={"uid": step.uid})
            resource = next(item for item in graph.resources if item.key == step.element)
            specification = registry.get_spec(resource.key.category, resource.type_key)
            if isinstance(step, OperationStep):
                reads, writes = set(), set(step.outputs)
            else:
                graph_specification = GraphElementSpec.require(specification)
                reads, writes = set(graph_specification.reads), set(graph_specification.writes)
            rid, type_key = step.element.rid, resource.type_key
        else:
            card = ElementCard(
                uid=step.uid,
                category=ResourceCategory.NODE,
                type_key="program",
                name=step.program.program_id if isinstance(step.program, ProgramRef) else step.uid,
            )
            reads, writes = set(), set(step.outputs)
            rid, type_key = step.uid, "program"
        cards[step.uid] = card
        route = conditions.get(step.uid)
        plan.add_step(
            Step(
                uid=step.uid,
                category=ResourceCategory.NODE,
                rid=rid,
                type_key=type_key,
                reads=reads,
                writes=writes,
                after=[source for source, targets in graph.edges.items() if step.uid in targets],
                branches=route.branches if route else {},
                meta=step.metadata.model_copy(
                    update={
                        "display_name": step.metadata.display_name or card.name,
                    }
                ),
            )
        )
    result = {}
    for step in graph.steps:
        route = conditions.get(step.uid)
        successors = set(graph.edges.get(step.uid, ()))
        if route:
            successors.update(route.branches.values())
        result[step.uid] = StepContext(
            uid=step.uid,
            metadata=step.metadata.model_copy(
                update={
                    "display_name": step.metadata.display_name or cards[step.uid].name,
                }
            ),
            adjacent_nodes=AdjacentNodes.from_dict({uid: cards[uid] for uid in successors}),
            branches=route.branches if route else {},
            topology=FinalizerAnalyzer(output_channel="output").analyze_node_topology(
                plan=plan,
                from_node_uid=step.uid,
                adjacent_node_uids=sorted(successors),
            ),
        )
    return result
