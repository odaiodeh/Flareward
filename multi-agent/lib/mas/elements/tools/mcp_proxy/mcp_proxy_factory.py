"""Pure construction; provider discovery is awaited by the element scope."""

from typing import Any

from mas.application.elements.factory import BaseFactory
from mas.application.ports.tool_provider import ToolProvider

from .config import McpProxyToolConfig
from .identifiers import Identifier
from .provider_tool import ProviderTool


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
