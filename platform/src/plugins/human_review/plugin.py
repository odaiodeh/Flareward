"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="human_review",
    version="1.0.0",
    elements=("plugins.human_review.elements.specification",),
    programs=("plugins.human_review.programs.human_review",),
)
