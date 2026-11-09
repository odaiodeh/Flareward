"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="agents",
    version="1.0.0",
    elements=(
        "plugins.agents.elements.custom_agent.spec",
        "plugins.agents.elements.custom_agent.spec.spec",
    ),
    programs=(),
)
