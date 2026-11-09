"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="codex",
    version="1.0.0",
    elements=("plugins.codex.specification",),
    programs=(),
)
