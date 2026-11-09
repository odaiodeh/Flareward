"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="ssh",
    version="1.0.0",
    elements=(
        "plugins.ssh.elements.ssh_exec.spec",
        "plugins.ssh.elements.ssh_exec.spec.spec",
    ),
    programs=(),
)
