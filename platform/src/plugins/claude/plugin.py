"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="claude",
    version="1.0.0",
    elements=(
        "plugins.claude.elements.claude_agent.spec",
        "plugins.claude.elements.claude_agent.spec.spec",
    ),
    programs=(),
)
