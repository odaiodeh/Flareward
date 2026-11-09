"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="openai",
    version="1.0.0",
    elements=(
        "plugins.openai.elements.openai.spec",
        "plugins.openai.elements.openai.spec.spec",
    ),
    programs=(),
)
