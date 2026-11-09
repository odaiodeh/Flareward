"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="adlc",
    version="1.0.0",
    elements=(),
    programs=(
        "plugins.adlc.programs.coding",
        "plugins.adlc.programs.design",
        "plugins.adlc.programs.designer",
        "plugins.adlc.programs.feature",
        "plugins.adlc.programs.program",
    ),
)
