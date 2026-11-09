from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.deep_agent.elements.deep_agent.card_builder import DeepAgentCardBuilder
from plugins.deep_agent.elements.deep_agent.config import DeepAgentNodeConfig
from plugins.deep_agent.elements.deep_agent.deep_agent_node import DeepAgentNode
from plugins.deep_agent.elements.deep_agent.deep_agent_node_factory import (
    DeepAgentNodeFactory,
)
from plugins.deep_agent.elements.deep_agent.identifiers import META, Identifier
from plugins.deep_agent.elements.deep_agent.validator import DeepAgentNodeValidator


class DeepAgentNodeElementSpec(GraphElementSpec):
    """Element specification for Deep Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = DeepAgentNodeConfig
    factory_cls = DeepAgentNodeFactory
    validator_cls = DeepAgentNodeValidator
    card_builder_cls = DeepAgentCardBuilder
    reads = DeepAgentNode.total_reads()
    writes = DeepAgentNode.total_writes()
    tags = META.tags
