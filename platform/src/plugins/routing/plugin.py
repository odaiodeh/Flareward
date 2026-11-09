"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="routing",
    version="1.0.0",
    elements=(
        "plugins.routing.elements.branch_chooser.spec",
        "plugins.routing.elements.branch_chooser.spec.spec",
        "plugins.routing.elements.router_boolean.spec",
        "plugins.routing.elements.router_boolean.spec.spec",
        "plugins.routing.elements.router_direct.spec",
        "plugins.routing.elements.router_direct.spec.spec",
        "plugins.routing.elements.threshold.spec",
        "plugins.routing.elements.threshold.spec.spec",
    ),
    programs=(),
)
