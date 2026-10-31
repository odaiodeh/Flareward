from __future__ import annotations

import asyncio
import logging

from mcp.types import Tool
from pydantic import HttpUrl

from mas.core.auth.credentials.credential import AuthCredential
from mas.core.auth.errors import AuthNotConfiguredError
from mas.elements.providers.mcp_server_client.mcp_server_client import McpServerClient
from mas.elements.tools.mcp_proxy.mcp_proxy_tool import McpProxyTool

from .provider_tool_registry import ProviderToolRegistry
from .transport.enums import McpTransportType

logger = logging.getLogger(__name__)


class McpProvider:
    """
    MCP Provider for managing tool discovery and creation.

    Handles the complete lifecycle of MCP tools from server discovery
    to tool instantiation. Optimizes performance through intelligent
    caching while maintaining thread safety across different execution
    contexts.

    The provider uses a single connection during initialization to
    discover and cache all tool metadata, then creates lightweight
    tool instances that use fresh connections for actual execution.

    Attributes:
        mcp_url: MCP server endpoint URL
        tool_names: List of specific tools to create (None for all)
        headers: Optional HTTP headers for authentication
        tools: List of created MCP proxy tool instances
    """

    def __init__(
        self,
        mcp_url: HttpUrl,
        tool_names: list[str] | None = None,
        headers: dict[str, str] | None = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
        auth: AuthCredential | None = None,
    ):
        """
        Initialize MCP provider for the specified server.

        Args:
            mcp_url: MCP server endpoint URL for communication
            tool_names: Specific tool names to create (None discovers all)
            headers: Optional HTTP headers for authentication (e.g., bearer token)
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
            auth: Optional AuthCredential for live token refresh
        """
        self.mcp_url = mcp_url
        self.tool_names = tool_names or []
        self.headers = headers or {}
        self.transport_type = transport_type
        self._auth = auth
        self._tools: list[McpProxyTool] = []
        self._initialized = False
        self._initialization_lock = asyncio.Lock()

        self._tool_registry = ProviderToolRegistry()

    async def _get_current_headers(self) -> dict[str, str]:
        """Merge static headers with live auth headers.

        Auth headers go first, static headers (additional_headers)
        overlay so custom headers like X-MCP-Realm are never lost.
        """
        current = {}
        if self._auth:
            authenticated = await self._auth.get_headers()
            if not authenticated:
                raise AuthNotConfiguredError(
                    "Bound credential did not provide authentication headers"
                )
            current.update(authenticated)
        if self.headers:
            current.update(self.headers)
        return current

    async def _initialize_tools(self) -> None:
        async with self._initialization_lock:
            if not self._initialized:
                await self._discover_tools()

    async def _discover_tools(self) -> None:
        """
        Discover and cache tool metadata from the server.

        Establishes a connection to the MCP server, discovers available
        tools, caches their metadata, and creates tool instances. Uses
        a single connection for efficiency while maintaining thread safety
        for subsequent tool usage.
        """
        if self._initialized:
            return

        init_headers = await self._get_current_headers()
        async with McpServerClient(
            mcp_url=self.mcp_url,
            headers=init_headers,
            transport_type=self.transport_type,
        ) as mcp_client:
            # Fetch all available tools in one go
            available_tools = await mcp_client.get_tools()

            # Cache tools in provider registry
            self._tool_registry.cache_tools(available_tools)

            # If no specific tool names provided, use all available
            if not self.tool_names:
                self.tool_names = [tool.name for tool in available_tools]

        self._tools = []
        for tool_name in self.tool_names:
            cached_tool_info = self._tool_registry.get_cached_tool_by_name(tool_name)
            if cached_tool_info:
                tool = McpProxyTool.create_with_cached_schema(
                    tool_name,
                    self.mcp_url,
                    cached_tool_info,
                    headers=self.headers,
                    transport_type=self.transport_type,
                    header_provider=self._get_current_headers,
                    auth_credential=self._auth,
                )
                self._tools.append(tool)
            else:
                logging.warning(f"Tool '{tool_name}' not found in available tools")

        self._initialized = True

    def get_cached_tool_info(self, tool_name: str) -> Tool | None:
        """
        Retrieve cached metadata for a specific tool.

        Returns tool information from the local cache without requiring
        a server connection. Useful for schema validation and tool
        introspection after provider initialization.

        Args:
            tool_name: Name of the tool to look up

        Returns:
            Tool metadata if cached, None if not found or not cached
        """
        return self._tool_registry.get_cached_tool_by_name(tool_name)

    async def get_tools(self) -> list[McpProxyTool]:
        """
        Retrieve all available MCP proxy tools.

        Returns the complete list of tool instances created by this
        provider. Automatically initializes the provider if not already
        done, discovering tools from the server on first access.

        Returns:
            List of McpProxyTool instances ready for execution
        """
        # Ensure tools are initialized before returning
        if not self._initialized:
            await self._initialize_tools()
        return self._tools

    async def get_tool_by_name(self, name: str) -> McpProxyTool | None:
        """
        Find a specific tool by its name.

        Searches the provider's tool collection for a tool with the
        exact specified name. Automatically initializes the provider
        if needed to discover available tools.

        Args:
            name: Exact name of the tool to find

        Returns:
            McpProxyTool instance if found, None if no match
        """
        # Ensure tools are initialized before searching
        if not self._initialized:
            await self._initialize_tools()
        for tool in self._tools:
            if tool.name == name:
                return tool
        return None

    async def refresh_tools(self) -> None:
        """
        Refresh all tools by reinitializing them.
        """
        self._initialized = False
        self._tools.clear()
        self._tool_registry.clear_cache()
        await self._initialize_tools()

    def clone(self) -> McpProvider:
        """
        Create a new McpProvider with the same configuration.
        """
        return McpProvider(
            mcp_url=self.mcp_url,
            tool_names=self.tool_names.copy() if self.tool_names else None,
            headers=self.headers.copy() if self.headers else None,
            transport_type=self.transport_type,
            auth=self._auth,
        )

    @property
    def is_initialized(self) -> bool:
        """Check if the provider has been initialized."""
        return self._initialized

    @property
    def tool_count(self) -> int:
        """Get the number of tools in this provider."""
        return len(self._tools)

    @property
    def cached_tool_count(self) -> int:
        """Get the number of cached tools in the registry."""
        cached_tools = self._tool_registry.get_cached_tools()
        return len(cached_tools) if cached_tools else 0

    def __str__(self) -> str:
        return (
            f"McpProvider(endpoint='{self.mcp_url}', "
            f"transport={self.transport_type.value}, "
            f"tools={len(self._tools)}, cached={self.cached_tool_count})"
        )

    @classmethod
    async def create_async(
        cls,
        mcp_url: HttpUrl,
        tool_names: list[str] | None = None,
        headers: dict[str, str] | None = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
        auth: AuthCredential | None = None,
    ) -> McpProvider:
        """
        Async factory method for creating a fully initialized McpProvider.
        """
        provider = cls(
            mcp_url,
            tool_names,
            headers,
            transport_type=transport_type,
            auth=auth,
        )
        await provider._initialize_tools()
        return provider

    def __repr__(self) -> str:
        tool_names_str = ", ".join(self.tool_names) if self.tool_names else "all"
        return (
            f"McpProvider(mcp_url='{self.mcp_url}', "
            f"transport_type={self.transport_type.value}, "
            f"tool_names=[{tool_names_str}], initialized={self._initialized})"
        )
