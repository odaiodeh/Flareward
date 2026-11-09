"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="web",
    version="1.0.0",
    elements=(
        "plugins.web.elements.web_fetch.spec",
        "plugins.web.elements.web_fetch.spec.spec",
    ),
    programs=(),
)
