"""Explicit feature-owned plugin contributions."""

from lumora.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="openai_compatible",
    version="1.0.0",
    elements=(
        "plugins.openai_compatible.elements.openai_compatible.spec",
        "plugins.openai_compatible.elements.openai_compatible.spec.spec",
    ),
    programs=(),
)
