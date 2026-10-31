"""Build full-graph element context from configuration, without constructing clients."""

from mas.application.elements.catalog.card_service import ElementCardService
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.references import references
from mas.core.element_meta import ElementConfigMeta
from mas.core.enums import ResourceCategory
from mas.domain.element_card import ElementCard
from mas.graph.graph_plan import GraphPlan
from mas.graph.models.adjacency import AdjacentNodes
from mas.graph.models.step_context import StepContext
from mas.graph.models.workflow import Step
from mas.graph.topology.finalizer_analyzer import FinalizerAnalyzer
from mas.programs.models import ElementStep, GraphDefinition


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
        if isinstance(step, ElementStep):
            card = resource_cards[step.element.rid].model_copy(update={"uid": step.uid})
            resource = next(item for item in graph.resources if item.key == step.element)
            specification = registry.get_spec(resource.key.category, resource.type_key)
            reads, writes = set(specification.reads), set(specification.writes)
            rid, type_key = step.element.rid, resource.type_key
        else:
            card = ElementCard(
                uid=step.uid,
                category=ResourceCategory.NODE,
                type_key="program",
                name=step.program.program_id,
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
