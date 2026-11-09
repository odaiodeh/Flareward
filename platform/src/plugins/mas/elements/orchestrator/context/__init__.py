"""
Orchestrator context system for rich, context-aware orchestration.

Provides specialized analyzers and models for understanding:
- Why cycles are triggered
- User intent (new task vs follow-up)
- Work plan health (futility, stalls, blocked items)
- Progress metrics across cycles
- Phase transition history
"""

from plugins.mas.elements.orchestrator.context.analyzers import (
    HealthAnalyzer,
    ProgressTracker,
)
from plugins.mas.elements.orchestrator.context.builder import OrchestratorContextBuilder
from plugins.mas.elements.orchestrator.context.models import (
    CycleTrigger,
    CycleTriggerReason,
    FutilityIndicator,
    OrchestratorContext,
    OrchestratorCycle,
    PendingCycle,
    PhaseHistory,
    PhaseTransition,
    ProgressMetrics,
    TriggerEvent,
    WorkPlanHealth,
)

__all__ = [
    # Enums
    "CycleTriggerReason",
    # Models
    "CycleTrigger",
    "PendingCycle",
    "TriggerEvent",
    "OrchestratorCycle",
    "FutilityIndicator",
    "ProgressMetrics",
    "WorkPlanHealth",
    "PhaseTransition",
    "PhaseHistory",
    "OrchestratorContext",
    # Analyzers
    "HealthAnalyzer",
    "ProgressTracker",
    # Builder
    "OrchestratorContextBuilder",
]
