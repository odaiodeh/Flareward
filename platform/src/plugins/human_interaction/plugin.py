"""Explicit feature-owned plugin contributions."""

from lumora.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="human_interaction",
    version="1.0.0",
    elements=(
        "plugins.human_interaction.elements.user_question.spec",
        "plugins.human_interaction.elements.user_question.spec.spec",
    ),
    programs=(),
)
