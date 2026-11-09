"""
Tool Interface for MCP Server Communication

Provides a clean abstraction layer for tool operations without caching.
Handles direct communication with MCP server through transport layer.
"""

import logging
from typing import Any, Dict, List, Optional

from mcp.types import CallToolResult, Tool

from plugins.mcp.elements.mcp_server_client.transport.base_transport import (
    BaseTransportManager,
    McpConnectionError,
)

logger = logging.getLogger(__name__)


class ToolInterface:
    """
    Clean interface for MCP tool operations.

    Provides a simple, consistent API for tool discovery and execution
    without caching complexity. All operations are delegated directly
    to the transport layer for immediate server communication.

    This interface abstracts away the low-level session management
    while maintaining clean, readable method calls.
    """

    def __init__(self, transport: BaseTransportManager):
        """
        Initialize the tool interface with a transport manager.

        Args:
            transport: BaseTransportManager instance for server communication
        """
        self.transport = transport

    async def get_tools(self, refresh: bool = False) -> List[Tool]:
        """
        Retrieve all available tools from the MCP server.

        Fetches the complete list of tools supported by the connected
        MCP server. Each tool includes metadata such as name, description,
        and input schema for validation.

        Args:
            refresh: Included for API compatibility, but ignored as this
                    interface does not cache results

        Returns:
            List of Tool objects with complete metadata

        Raises:
            McpConnectionError: If the server request fails
        """
        try:
            session = self.transport._session  # type: ignore
            tool_list = await session.list_tools()
            logger.debug(f"Retrieved {len(tool_list.tools)} tools from server")
            return tool_list.tools
        except Exception as e:
            logger.error(f"Failed to retrieve tools: {e}")
            raise McpConnectionError(f"Failed to fetch tools: {e}")

    async def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """
        Find a specific tool by its name.

        Searches through all available tools to find one matching
        the specified name. Returns the complete tool metadata
        including description and input schema.

        Args:
            name: Exact name of the tool to find

        Returns:
            Tool object if found, None if no match exists

        Raises:
            McpConnectionError: If server communication fails
        """
        try:
            tools = await self.get_tools()
            tool = next((t for t in tools if t.name == name), None)
            if tool:
                logger.debug(f"Found tool '{name}'")
            else:
                logger.debug(f"Tool '{name}' not found among {len(tools)} available tools")
            return tool
        except Exception as e:
            logger.error(f"Failed to find tool '{name}': {e}")
            raise McpConnectionError(f"Failed to get tool '{name}': {e}")

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """
        Execute a tool on the MCP server.

        Sends a tool execution request to the server with the specified
        arguments. The server processes the request and returns results
        which may include text, images, or other content types.

        Args:
            tool_name: Name of the tool to execute
            arguments: Dictionary of parameters for tool execution

        Returns:
            CallToolResult containing the execution results

        Raises:
            McpConnectionError: If tool execution fails or server disconnects
        """
        try:
            session = self.transport._session  # type: ignore
            result = await session.call_tool(tool_name, arguments)
            logger.debug(f"Successfully executed tool '{tool_name}'")
            return result
        except Exception as e:
            logger.error(f"Tool execution failed for '{tool_name}': {e}")
            # Force disconnect on error to ensure clean reconnection
            await self.transport.disconnect()
            raise McpConnectionError(f"Failed to execute tool '{tool_name}': {e}")
