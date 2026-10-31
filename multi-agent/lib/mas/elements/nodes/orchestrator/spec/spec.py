from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..config import OrchestratorNodeConfig
from ..identifiers import META, Identifier
from ..orchestrator_node import OrchestratorNode
from ..orchestrator_node_factory import OrchestratorNodeFactory
from ..validator import OrchestratorNodeValidator


class OrchestratorNodeElementSpec(BaseElementSpec):
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
