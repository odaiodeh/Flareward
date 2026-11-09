from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.mas.elements.orchestrator.config import OrchestratorNodeConfig
from plugins.mas.elements.orchestrator.identifiers import META, Identifier
from plugins.mas.elements.orchestrator.orchestrator_node import OrchestratorNode
from plugins.mas.elements.orchestrator.orchestrator_node_factory import (
    OrchestratorNodeFactory,
)
from plugins.mas.elements.orchestrator.validator import OrchestratorNodeValidator


class OrchestratorNodeElementSpec(GraphElementSpec):
    """Element specification for Orchestrator Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = OrchestratorNodeConfig
    factory_cls = OrchestratorNodeFactory
    reads = OrchestratorNode.total_reads()
    writes = OrchestratorNode.total_writes()
    tags = META.tags
    validator_cls = OrchestratorNodeValidator
