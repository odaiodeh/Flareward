"""Optional external retrieval capability, independent of a bundled RAG service."""

from flareward.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    key="retrieval",
    version="1.0.0",
    elements=(
        "plugins.retrieval.elements.slack.spec",
        "plugins.retrieval.elements.slack.spec.spec",
    ),
)
