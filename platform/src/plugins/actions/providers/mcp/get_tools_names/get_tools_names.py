from __future__ import annotations

from typing import Any

from pydantic import Field, HttpUrl

from lumora.resources.domain.categories import ResourceCategory
from lumora.services.actions.contracts import (
    ActionContext,
    ActionType,
    BaseAction,
    BaseActionInput,
    BaseActionOutput,
)
from lumora.services.auth.service import AuthService
from plugins.mcp.elements.mcp_server_client.config import McpProviderConfig
from plugins.mcp.elements.mcp_server_client.identifiers import Identifier
from plugins.mcp.elements.mcp_server_client.mcp_provider_factory import McpProviderFactory
from plugins.mcp.elements.mcp_server_client.transport.enums import McpTransportType


# Input/Output models for this action
class GetToolsNamesInput(BaseActionInput):
    """Input for MCP tools discovery"""

    mcp_url: HttpUrl
    transport_type: McpTransportType = Field(
        default=McpTransportType.STREAMABLE_HTTP,
        description="Transport protocol for MCP server communication",
    )
    additional_headers: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional HTTP headers to include in MCP server requests",
    )
    user_id: str = Field(default="")
    server_identifier: str = Field(default="")


class GetToolsNamesOutput(BaseActionOutput):
    """Output for MCP tools discovery"""

    tool_names: list[str] = []
    total_count: int = 0


class GetToolsNamesAction(BaseAction[GetToolsNamesInput, GetToolsNamesOutput]):
    uid = "mcp.get_tools_names"
    name = "get_tools_names"
    description = "Retrieve the list of available tool names from the MCP server"
    action_type = ActionType.DISCOVERY
    input_schema = GetToolsNamesInput
    output_schema = GetToolsNamesOutput
    version = "1.1.0"
    tags = frozenset({"mcp", "discovery", "tools"})
    elements = frozenset({(ResourceCategory.PROVIDER.value, Identifier.TYPE)})

    def __init__(
        self, factory: McpProviderFactory | None = None, auth_service: AuthService | None = None
    ):
        """
        Initialize action with optional factory injection.

        Args:
            factory: McpProviderFactory instance (creates default if not provided)
        """
        super().__init__()
        self._factory = factory or McpProviderFactory()
        self._auth_service = auth_service

    async def execute(
        self,
        input_data: GetToolsNamesInput,
        context: ActionContext | None = None,
    ) -> GetToolsNamesOutput:
        """
        Execute tools discovery asynchronously.

        Args:
            input_data: Validated discovery input
            context: Optional execution context (element configs, etc.)

        Returns:
            Discovery result with tool names and count
        """
        try:
            config = McpProviderConfig(
                mcp_url=input_data.mcp_url,
                transport_type=input_data.transport_type,
                additional_headers=input_data.additional_headers,
            )

            auth = None
            if self._auth_service and input_data.user_id and input_data.server_identifier:
                auth = await self._auth_service.bind_async(
                    input_data.user_id, input_data.server_identifier
                )

            provider = await self._factory.create_async(config, auth_credential=auth)
            tools = await provider.get_tools()
            tool_names = [tool.name for tool in tools]

            return GetToolsNamesOutput(
                success=True,
                message=f"Found {len(tool_names)} tools",
                tool_names=tool_names,
                total_count=len(tool_names),
            )

        except Exception:
            return GetToolsNamesOutput(
                success=False,
                message="Failed to retrieve tools",
                tool_names=[],
                total_count=0,
            )
