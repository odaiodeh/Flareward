from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory

from ..config import MockAgentNodeConfig
from ..identifiers import META, Identifier
from ..mock_agent import MockAgentNode
from ..mock_agent_node_factory import MockAgentNodeFactory


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
