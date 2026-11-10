from lumora.elements.specification import BaseElementSpec
from lumora.elements.tools.configuration.card_builder import ToolCardBuilder
from lumora.resources.domain.categories import ResourceCategory
from plugins.mcp.elements.mcp_proxy.config import McpProxyToolConfig
from plugins.mcp.elements.mcp_proxy.identifiers import META, Identifier
from plugins.mcp.elements.mcp_proxy.mcp_proxy_factory import McpProxyToolFactory


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
