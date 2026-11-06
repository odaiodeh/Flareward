"""
Claude Agent Node Specification
"""

from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory

from ..card_builder import ClaudeAgentCardBuilder
from ..claude_agent_node import ClaudeAgentNode
from ..claude_agent_node_factory import ClaudeAgentNodeFactory
from ..config import ClaudeAgentNodeConfig
from ..identifiers import META, Identifier
from ..validator import ClaudeAgentNodeValidator


class ClaudeAgentNodeElementSpec(GraphElementSpec):
    """Element specification for Claude Agent Node."""

    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = ClaudeAgentNodeConfig
    factory_cls = ClaudeAgentNodeFactory
    validator_cls = ClaudeAgentNodeValidator
    card_builder_cls = ClaudeAgentCardBuilder
    reads = ClaudeAgentNode.total_reads()
    writes = ClaudeAgentNode.total_writes()
    tags = META.tags
