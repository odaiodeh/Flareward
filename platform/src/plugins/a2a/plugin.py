"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="a2a",
    version="1.0.0",
    elements=(
        "plugins.a2a.elements.a2a_agent.spec",
        "plugins.a2a.elements.a2a_agent.spec.spec",
    ),
    programs=(),
)
