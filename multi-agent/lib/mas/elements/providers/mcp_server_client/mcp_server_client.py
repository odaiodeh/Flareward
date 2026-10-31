import asyncio
import logging
from typing import Dict, Any, Optional, List
from pydantic import HttpUrl
from yarl import URL
from mcp.types import Tool, CallToolResult, CreateMessageRequestParams, CreateMessageResult, TextContent
import anyio

from .transport.base_transport import BaseTransportManager, McpConnectionError
from .transport.enums import McpTransportType
from .transport.transport_factory import TransportFactory
from .tool_interface import ToolInterface

logger = logging.getLogger(__name__)


class McpProxyToolError(Exception):
    """Any error that occurs while proxying to an MCP tool."""
    pass


class McpServerClient:
    """
    MCP Server Client for direct server communication.

    Manages connections to MCP servers and provides a clean interface
    for tool discovery and execution. Handles connection lifecycle,
    reference counting for shared usage, and automatic reconnection.

    The client provides thread-safe connection sharing through context
    manager usage, allowing multiple operations to share a single
    connection efficiently.

    Attributes:
        tools: ToolInterface for clean tool operations
        transport: BaseTransportManager for connection handling
        mcp_url: Server endpoint URL
        headers: Optional HTTP headers for authentication or custom metadata
        transport_type: The transport protocol used for this connection
    """

    _transport_factory = TransportFactory()

    def __init__(
        self,
        mcp_url: HttpUrl,
        headers: Optional[Dict[str, str]] = None,
        transport_type: McpTransportType = McpTransportType.STREAMABLE_HTTP,
    ):
        """
        Initialize MCP server client.

        Sets up transport layer and tool interface for communication
        with the specified MCP server endpoint. Configures connection
        sharing and reference counting for efficient resource usage.

        Args:
            mcp_url: HTTP(S) URL of the MCP server endpoint
            headers: Optional HTTP headers for authentication or custom metadata
            transport_type: Transport protocol to use (SSE or Streamable HTTP)
        """
        self.mcp_url = str(mcp_url)
        self.headers = headers or {}
        self.transport_type = transport_type

        # Initialize transport layer via factory
        self.transport: BaseTransportManager = self._transport_factory.create(
            transport_type=self.transport_type,
            endpoint=self.mcp_url,
            sampling_callback=self._default_sampling_callback,
            headers=self.headers,
        )

        # Initialize clean tool interface
        self.tools = ToolInterface(self.transport)

        # Connection sharing state
        self._refcount = 0  # Active context manager users
        self._lock = anyio.Lock()  # Thread-safe operations

    async def _default_sampling_callback(
            self, message: CreateMessageRequestParams
    ) -> CreateMessageResult:
        """
        Handle server sampling requests.

        Provides a default response when the MCP server requests
        message sampling. This callback is used for server-initiated
        interactions during tool execution.

        Args:
            message: Sampling request parameters from server

        Returns:
            Default message result for sampling requests
        """
        return CreateMessageResult(
            role="assistant",
            content=TextContent(type="text", text="Default response"),
            model="unknown",
            stopReason="endTurn"
        )

    @property
    def is_connected(self) -> bool:
        """
        Check if client is currently connected to server.

        Returns:
            True if transport connection is active, False otherwise
        """
        return self.transport.is_connected

    async def connect(self) -> None:
        """
        Establish connection to MCP server.

        Opens the underlying transport connection to the server.
        This method is typically called automatically through
        context manager usage, but can be used for explicit
        connection management.

        Raises:
            McpConnectionError: If connection establishment fails
        """
        try:
            await self.transport.connect()
        except McpConnectionError as e:
            raise McpConnectionError(f"Failed to connect to server: {e}")

    async def disconnect(self) -> None:
        """
        Close connection to MCP server.

        Terminates the underlying transport connection. This method
        is typically called automatically when the last context
        manager exits, but can be used for explicit disconnection.

        Raises:
            McpConnectionError: If disconnection fails
        """
        try:
            await self.transport.disconnect()
        except McpConnectionError as e:
            raise McpConnectionError(f"Failed to disconnect from server: {e}")

    async def get_tools(self, refresh: bool = False) -> List[Tool]:
        """
        Retrieve all available tools from the server.

        Fetches the complete list of tools supported by the connected
        MCP server, including metadata such as descriptions and schemas.

        Args:
            refresh: Included for API compatibility (ignored)

        Returns:
            List of Tool objects with complete metadata

        Raises:
            McpConnectionError: If server communication fails
        """
        return await self.tools.get_tools(refresh=refresh)

    async def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """
        Find a specific tool by name.

        Searches for a tool with the exact specified name among
        all tools available on the server.

        Args:
            name: Exact name of the tool to find

        Returns:
            Tool object if found, None if no match exists

        Raises:
            McpConnectionError: If server communication fails
        """
        return await self.tools.get_tool_by_name(name)

    async def call_tool(
            self,
            tool_name: str,
            arguments: Dict[str, Any]
    ) -> CallToolResult:
        """
        Execute a tool on the MCP server.

        Sends a tool execution request with the specified arguments
        and returns the results. The server processes the request
        and may return text, images, or other content types.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of parameters for tool execution

        Returns:
            CallToolResult containing the execution results

        Raises:
            McpConnectionError: If tool execution fails
        """
        return await self.tools.call_tool(tool_name, arguments)

    async def __aenter__(self):
        """
        Enter the client context manager.

        Manages connection reference counting to allow multiple
        concurrent context manager users to share a single connection.
        Connects to the server only on the first entry.

        Returns:
            Self for use in 'async with' statements
        """
        async with self._lock:
            if self._refcount == 0:
                # Nobody's connected yet → open the HTTP transport + session
                await self.transport.connect()
            self._refcount += 1
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """
        Exit the client context manager.

        Decrements the reference count and disconnects from the
        server when the last context manager exits. Ensures clean
        resource cleanup when all users are finished.

        Args:
            exc_type: Exception type if an error occurred
            exc: Exception instance if an error occurred
            tb: Traceback if an error occurred
        """
        async with self._lock:
            self._refcount -= 1
            # Only the last exiting context actually tears down the connection
            if self._refcount == 0:
                await self.transport.disconnect()

    def clone(self) -> "McpServerClient":
        """
        Create a new client instance with the same configuration.

        Returns a fresh client configured for the same server endpoint.
        The new client will have its own connection state and reference
        counting, independent of the original client.

        Returns:
            New McpServerClient instance for the same endpoint
        """
        return McpServerClient(
            mcp_url=self.mcp_url,
            headers=self.headers,
            transport_type=self.transport_type,
        )
