"""
Claude Agent Node Specification
"""

from lumora.programs.graph_elements import GraphElementSpec
from lumora.resources.domain.categories import ResourceCategory
from plugins.claude.elements.claude_agent.card_builder import ClaudeAgentCardBuilder
from plugins.claude.elements.claude_agent.claude_agent_node import ClaudeAgentNode
from plugins.claude.elements.claude_agent.claude_agent_node_factory import (
    ClaudeAgentNodeFactory,
)
from plugins.claude.elements.claude_agent.config import ClaudeAgentNodeConfig
from plugins.claude.elements.claude_agent.identifiers import META, Identifier
from plugins.claude.elements.claude_agent.validator import ClaudeAgentNodeValidator


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
