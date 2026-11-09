"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="openshift",
    version="1.0.0",
    elements=(
        "plugins.openshift.elements.oc_exec.spec",
        "plugins.openshift.elements.oc_exec.spec.spec",
    ),
    programs=(),
)
