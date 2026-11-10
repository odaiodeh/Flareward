from typing import Literal

from pydantic import Field

from lumora.elements.hints import CardContext, CardHint
from lumora.elements.tools.configuration.base_config import BaseToolConfig
from lumora.resources.domain.references import ProviderRef
from plugins.mcp.elements.mcp_proxy.identifiers import Identifier


class McpProxyToolConfig(BaseToolConfig):
    """
    Configuration for the Mcp Proxy tool.
    """

    type: Literal[Identifier.TYPE] = Identifier.TYPE
    provider: ProviderRef = Field(description="Provider supplying the selected MCP tool")
    tool_name: str = Field(
        ...,
        min_length=1,
        description="Exact tool name exposed by the provider",
        json_schema_extra=CardHint(contexts=[CardContext.BUILTIN, CardContext.CUSTOM]).to_hints(),
    )
