"""Explicit feature-owned plugin contributions."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="gemini",
    version="1.0.0",
    elements=(
        "plugins.gemini.elements.google_genai.spec",
        "plugins.gemini.elements.google_genai.spec.spec",
    ),
    programs=(),
)
