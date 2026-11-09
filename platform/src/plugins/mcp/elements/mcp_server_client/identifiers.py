from dataclasses import dataclass
from enum import Enum
from typing import List


class Identifier(str, Enum):
    """Machine-readable key for MCP Server Provider."""

    TYPE = "mcp_server"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: List[str]


META = Meta(
    name="MCP Provider",
    description="Remote MCP service via HTTPS/SSE",
    tags=["provider", "mcp", "server", "client", "websocket", "sse"],
)
