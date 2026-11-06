"""
A2A Agent Node Specification
"""

from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory

from ..a2a_agent_node import A2AAgentNode
from ..a2a_agent_node_factory import A2AAgentNodeFactory
from ..card_builder import A2AAgentCardBuilder
from ..config import A2AAgentNodeConfig
from ..identifiers import META, Identifier
from ..validator import A2AAgentNodeValidator


class A2AAgentNodeElementSpec(GraphElementSpec):
    """Element specification for A2A Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = A2AAgentNodeConfig
    factory_cls = A2AAgentNodeFactory
    validator_cls = A2AAgentNodeValidator
    card_builder_cls = A2AAgentCardBuilder
    reads = A2AAgentNode.total_reads()
    writes = A2AAgentNode.total_writes()
    tags = META.tags
