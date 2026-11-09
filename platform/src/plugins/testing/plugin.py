"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="testing",
    version="1.0.0",
    elements=(
        "plugins.testing.elements.mock.spec",
        "plugins.testing.elements.mock.spec.spec",
        "plugins.testing.elements.mock_agent.spec",
        "plugins.testing.elements.mock_agent.spec.spec",
        "plugins.testing.specification",
    ),
    programs=(
        "plugins.testing.programs.git_check",
        "plugins.testing.programs.python_check",
    ),
)
