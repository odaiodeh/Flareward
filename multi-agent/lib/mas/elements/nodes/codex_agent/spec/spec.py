"""Discoverable Codex coding-agent element."""

from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory

from ..codex_agent_node import CodexAgentNode
from ..codex_agent_node_factory import CodexAgentNodeFactory
from ..config import CodexAgentNodeConfig
from ..identifiers import META, Identifier


class CodexAgentNodeElementSpec(BaseElementSpec):
    category = ResourceCategory.NODE
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = CodexAgentNodeConfig
    factory_cls = CodexAgentNodeFactory
    reads = CodexAgentNode.total_reads()
    writes = CodexAgentNode.total_writes()
    tags = META.tags
