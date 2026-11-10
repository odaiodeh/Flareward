"""
A2A Agent Node Specification
"""

from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.a2a.elements.a2a_agent.a2a_agent_node import A2AAgentNode
from plugins.a2a.elements.a2a_agent.a2a_agent_node_factory import A2AAgentNodeFactory
from plugins.a2a.elements.a2a_agent.card_builder import A2AAgentCardBuilder
from plugins.a2a.elements.a2a_agent.config import A2AAgentNodeConfig
from plugins.a2a.elements.a2a_agent.identifiers import META, Identifier
from plugins.a2a.elements.a2a_agent.validator import A2AAgentNodeValidator


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
