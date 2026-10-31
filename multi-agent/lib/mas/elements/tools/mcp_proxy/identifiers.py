from dataclasses import dataclass
from enum import StrEnum


class Identifier(StrEnum):
    """Machine-readable key for the MCP Proxy tool."""

    TYPE = "mcp_proxy"


@dataclass(frozen=True)
class Meta:
    name: str
    description: str
    tags: list[str]


META = Meta(
    name="MCP Proxy Tool",
    description="Execute a MCP tool through MCP Server Provider",
    tags=["tool", "mcp", "proxy", "remote", "execution"],
)
