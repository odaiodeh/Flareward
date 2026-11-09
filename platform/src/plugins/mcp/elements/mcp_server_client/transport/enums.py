"""
Transport type enumeration for MCP connections.

Defines the supported transport protocols for communicating
with MCP servers.
"""

from enum import Enum


class McpTransportType(str, Enum):
    """
    Supported MCP transport protocols.

    Each value corresponds to a concrete TransportManager implementation
    that handles the protocol-specific connection details.
    """

    SSE = "sse"
    STREAMABLE_HTTP = "streamable http"
