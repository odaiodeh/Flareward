from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.agents.elements.custom_agent.card_builder import CustomAgentCardBuilder
from plugins.agents.elements.custom_agent.config import CustomAgentNodeConfig
from plugins.agents.elements.custom_agent.custom_agent import CustomAgentNode
from plugins.agents.elements.custom_agent.custom_agent_node_factory import (
    CustomAgentNodeFactory,
)
from plugins.agents.elements.custom_agent.identifiers import META, Identifier
from plugins.agents.elements.custom_agent.validator import CustomAgentNodeValidator


class CustomAgentNodeElementSpec(GraphElementSpec):
    """Element specification for Custom Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = CustomAgentNodeConfig
    factory_cls = CustomAgentNodeFactory
    reads = CustomAgentNode.total_reads()
    writes = CustomAgentNode.total_writes()
    tags = META.tags
    validator_cls = CustomAgentNodeValidator
    card_builder_cls = CustomAgentCardBuilder
