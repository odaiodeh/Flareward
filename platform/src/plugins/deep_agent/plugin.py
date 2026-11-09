"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="deep_agent",
    version="1.0.0",
    elements=(
        "plugins.deep_agent.elements.deep_agent.spec",
        "plugins.deep_agent.elements.deep_agent.spec.spec",
    ),
    programs=(),
)
