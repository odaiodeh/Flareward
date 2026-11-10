"""Explicit feature-owned plugin contributions."""

from lumora.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="verification",
    version="1.0.0",
    elements=("plugins.verification.elements.specification",),
    programs=("plugins.verification.programs.waiting",),
)
