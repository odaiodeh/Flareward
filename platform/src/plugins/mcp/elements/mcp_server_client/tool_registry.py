from typing import Any, Dict, List, Optional

from mcp.types import CallToolResult, Tool

from plugins.mcp.elements.mcp_server_client.transport.base_transport import (
    BaseTransportManager,
)


class McpToolError(Exception):
    """Raised for any MCP tool‐related error (missing, validation, runtime)."""

    pass


class ToolRegistry:
    """
    Responsible *only* for:
      1) Listing available tools (get_tools)
      2) Fetching a specific tool by name (get_tool_by_name)
      3) Invoking a tool (call_tool) + minimal JSON‐schema validation (`required` fields)

    Construction:
        registry = ToolRegistry(transport_manager, health_checker)

    Important:
        - Always call registry.get_tools() or registry.call_tool() inside an `await health.ensure_connected()`
    """

    def __init__(self, transport: BaseTransportManager):
        self.transport = transport
        self._tools_cache: Optional[List[Tool]] = None

    async def get_tools(self, refresh: bool = False) -> List[Tool]:
        """
        Return a list of all available tools. Cache the result unless `refresh=True`.
        Internally calls `await health.ensure_connected(force_check=True)`.
        """
        if not refresh and self._tools_cache is not None:
            return self._tools_cache

        try:
            session = self.transport._session  # type: ignore
            tool_list = await session.list_tools()
            self._tools_cache = tool_list.tools
            # TODO: Replace with proper logging when logging system is implemented
            # print("ToolRegistry: retrieved %d tools", len(self._tools_cache))
            return self._tools_cache
        except Exception as e:
            # TODO: Replace with proper logging when logging system is implemented
            # print("ToolRegistry: list_tools failed: %s", e)
            self._tools_cache = None
            raise McpToolError(f"Failed to fetch tools: {e}")

    async def get_tool_by_name(self, name: str) -> Optional[Tool]:
        """
        Return a single Tool object whose `tool.name == name`, or None if not found.
        """
        tools = await self.get_tools(refresh=False)
        return next((t for t in tools if t.name == name), None)

    async def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> CallToolResult:
        """
        1) Ensure we’re connected + healthy (force a connect if needed).
        2) Look up the tool by name. If missing, raise McpToolError.
        3) Do a minimal `required`‐field check against tool.inputSchema.
        4) Invoke `await session.call_tool(tool_name, arguments)` and return the raw CallToolResult.
           On any exception, disconnect transport and re‐raise as McpToolError.
        """
        # 1) Find the tool definition
        tool = await self.get_tool_by_name(tool_name)
        if tool is None:
            available = [t.name for t in await self.get_tools(refresh=False)]
            raise McpToolError(f"Tool '{tool_name}' not found. Available: {available}")

        # 2) Minimal “required” check
        schema = tool.inputSchema or {}
        required_fields = schema.get("required", [])
        missing = [f for f in required_fields if f not in arguments]
        if missing:
            raise McpToolError(f"Missing required arguments {missing} for tool '{tool_name}'")

        # 3) Actually call the tool
        try:
            session = self.transport._session  # type: ignore
            result = await session.call_tool(tool_name, arguments)
            # TODO: Replace with proper logging when logging system is implemented
            # print("ToolRegistry: called '%s' successfully", tool_name)
            return result
        except Exception as e:
            # TODO: Replace with proper logging when logging system is implemented
            # print("ToolRegistry: call_tool('%s') failed: %s", tool_name, e)
            # If the session broke, force a disconnect so that next call re‐connects
            await self.transport.disconnect()
            raise McpToolError(f"Failed to invoke tool '{tool_name}': {e}")
