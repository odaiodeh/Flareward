"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="artifacts",
    version="1.0.0",
    elements=("plugins.artifacts.elements.specification",),
    programs=(),
)
