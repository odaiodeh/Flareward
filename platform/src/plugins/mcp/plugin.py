"""Explicit feature-owned plugin contributions."""

from lumora.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="mcp",
    version="1.0.0",
    elements=(
        "plugins.mcp.elements.mcp_proxy.spec",
        "plugins.mcp.elements.mcp_proxy.spec.spec",
        "plugins.mcp.elements.mcp_server_client.spec",
        "plugins.mcp.elements.mcp_server_client.spec.spec",
    ),
    programs=(),
)
