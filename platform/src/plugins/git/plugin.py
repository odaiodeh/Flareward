"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="git",
    version="1.0.0",
    elements=("plugins.git.elements.specification",),
    programs=(),
)
