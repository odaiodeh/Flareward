"""
SSE (Server-Sent Events) transport manager for MCP connections.

Uses the ``mcp.client.sse.sse_client`` to open a unidirectional SSE
stream to the MCP server.
"""

from contextlib import AbstractAsyncContextManager
from typing import Any

from mcp.client.sse import sse_client

from .base_transport import BaseTransportManager
from .enums import McpTransportType


class SseTransportManager(BaseTransportManager):
    """
    MCP transport over Server-Sent Events (SSE).

    Supports custom HTTP headers (e.g. Bearer token authentication)
    passed through to the underlying HTTP client.
    """

    @property
    def transport_type(self) -> McpTransportType:
        return McpTransportType.SSE

    def _create_transport_context(self) -> AbstractAsyncContextManager[tuple[Any, Any]]:
        return sse_client(url=self.endpoint, headers=self.headers)
