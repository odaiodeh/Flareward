"""Explicit feature-owned plugin contributions."""

from lumora.plugins.models import PluginDefinition

PLUGIN = PluginDefinition(
    graph_validators=("plugins.mas.validation.orchestrator.validator:OrchestratorValidator",),
    key="mas",
    version="1.0.0",
    elements=(
        "plugins.mas.elements.final_answer.spec",
        "plugins.mas.elements.final_answer.spec.spec",
        "plugins.mas.elements.llm_merger.spec",
        "plugins.mas.elements.llm_merger.spec.spec",
        "plugins.mas.elements.orchestrator.spec",
        "plugins.mas.elements.orchestrator.spec.spec",
    ),
    programs=(),
)
