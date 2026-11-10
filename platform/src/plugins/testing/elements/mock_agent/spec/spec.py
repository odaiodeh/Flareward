from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.testing.elements.mock_agent.config import MockAgentNodeConfig
from plugins.testing.elements.mock_agent.identifiers import META, Identifier
from plugins.testing.elements.mock_agent.mock_agent import MockAgentNode
from plugins.testing.elements.mock_agent.mock_agent_node_factory import (
    MockAgentNodeFactory,
)


class MockAgentNodeElementSpec(GraphElementSpec):
    """Element specification for Mock Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = MockAgentNodeConfig
    factory_cls = MockAgentNodeFactory
    reads = MockAgentNode.total_reads()
    writes = MockAgentNode.total_writes()
    tags = META.tags
