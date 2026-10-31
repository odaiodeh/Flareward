from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.tools.common.card_builder import ToolCardBuilder

from ..config import McpProxyToolConfig
from ..identifiers import META, Identifier
from ..mcp_proxy_factory import McpProxyToolFactory


class McpProxyToolElementSpec(BaseElementSpec):
    """Element specification for MCP Proxy Tool."""

    category = ResourceCategory.TOOL
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = McpProxyToolConfig
    factory_cls = McpProxyToolFactory
    tags = META.tags
    card_builder_cls = ToolCardBuilder
