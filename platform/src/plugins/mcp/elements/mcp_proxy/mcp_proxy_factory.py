"""Pure construction; provider discovery is awaited by the element scope."""

from typing import Any

from flareward.elements.factory import BaseFactory
from flareward.elements.ports.tool_provider import ToolProvider
from plugins.mcp.elements.mcp_proxy.config import McpProxyToolConfig
from plugins.mcp.elements.mcp_proxy.identifiers import Identifier
from plugins.mcp.elements.mcp_proxy.provider_tool import ProviderTool


class McpProxyToolFactory(BaseFactory[McpProxyToolConfig, ProviderTool]):
    def accepts(self, cfg: McpProxyToolConfig, element_type: str) -> bool:
        return element_type == Identifier.TYPE

    def create(
        self,
        cfg: McpProxyToolConfig,
        *,
        provider: ToolProvider,
        **kwargs: Any,
    ) -> ProviderTool:
        return ProviderTool(cfg.tool_name, provider)
