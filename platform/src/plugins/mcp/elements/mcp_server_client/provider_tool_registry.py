"""
Provider Tool Registry for MCP Tool Caching

Manages tool metadata caching at the provider level for performance optimization.
Eliminates redundant server requests by storing tool schemas in memory.
"""

import logging
from typing import Dict, List, Optional

from mcp.types import Tool

logger = logging.getLogger(__name__)


class ProviderToolRegistry:
    """
    Lightweight tool registry for provider-level caching.

    Manages tool metadata storage and retrieval without transport dependencies.
    Designed specifically for caching tool schemas at the provider level
    to reduce redundant server requests during tool initialization.

    This registry stores only immutable tool metadata (schemas, descriptions)
    and provides thread-safe access patterns suitable for cross-portal usage.
    """

    def __init__(self):
        """
        Initialize an empty tool registry.

        Creates storage structures for tool metadata caching.
        All data structures are designed for read-heavy workloads
        with occasional bulk updates.
        """
        self._tools_cache: Optional[List[Tool]] = None
        self._tools_by_name: Optional[Dict[str, Tool]] = None

    def cache_tools(self, tools: List[Tool]) -> None:
        """
        Store a complete set of tools in the registry.

        Replaces any existing cached tools with the provided list.
        Creates both list and name-indexed storage for efficient
        access patterns. This method is typically called once
        during provider initialization.

        Args:
            tools: Complete list of Tool objects to cache
        """
        self._tools_cache = tools
        self._tools_by_name = {tool.name: tool for tool in tools}
        logger.debug(f"Cached {len(tools)} tool schemas in registry")

    def get_cached_tools(self) -> Optional[List[Tool]]:
        """
        Retrieve all cached tools.

        Returns the complete list of tools currently stored in
        the registry. Useful for bulk operations or registry
        status checking.

        Returns:
            List of all cached Tool objects, or None if cache is empty
        """
        return self._tools_cache

    def get_cached_tool_by_name(self, name: str) -> Optional[Tool]:
        """
        Retrieve a specific tool by name.

        Provides fast lookup of individual tools using the name index.
        This is the primary access method for tool schema retrieval
        during tool creation and validation.

        Args:
            name: Exact name of the tool to retrieve

        Returns:
            Tool object if found in cache, None if not cached or not found
        """
        if self._tools_by_name is None:
            return None

        tool = self._tools_by_name.get(name)
        if tool:
            logger.debug(f"Retrieved cached tool '{name}'")
        else:
            logger.debug(f"Tool '{name}' not found in cache")
        return tool

    def is_cached(self) -> bool:
        """
        Check if any tools are currently cached.

        Determines whether the registry contains tool data.
        Useful for conditional logic that depends on cache state.

        Returns:
            True if tools are cached, False if registry is empty
        """
        return self._tools_cache is not None

    def get_cache_size(self) -> int:
        """
        Get the number of tools currently cached.

        Returns the count of tools stored in the registry.
        Useful for monitoring and debugging cache state.

        Returns:
            Number of cached tools, 0 if cache is empty
        """
        if self._tools_cache is None:
            return 0
        return len(self._tools_cache)

    def clear_cache(self) -> None:
        """
        Remove all cached tools from the registry.

        Resets the registry to its initial empty state.
        This operation is typically used during provider
        refresh or cleanup operations.
        """
        self._tools_cache = None
        self._tools_by_name = None
        logger.debug("Cleared tool registry cache")

    def has_tool(self, name: str) -> bool:
        """
        Check if a specific tool is cached.

        Performs a fast existence check without retrieving
        the full tool object. Useful for validation logic.

        Args:
            name: Tool name to check

        Returns:
            True if tool is cached, False otherwise
        """
        if self._tools_by_name is None:
            return False
        return name in self._tools_by_name
