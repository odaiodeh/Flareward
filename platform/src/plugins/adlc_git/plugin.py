"""Explicit feature-owned plugin contributions."""

from lumora.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="adlc_git",
    version="1.0.0",
    elements=(),
    programs=("plugins.adlc_git.programs.coding",),
)
