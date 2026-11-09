"""Phase management system for agents."""

# Core phase models and protocols
# Utility modules
from flareward.elements.agents.phases import phase_guidance, phase_tools
from flareward.elements.agents.phases.extensible_phases import (
    ExtensiblePhaseProvider,
    PhaseRegistry,
)
from flareward.elements.agents.phases.flexible_phase_provider import FlexiblePhaseProvider
from flareward.elements.agents.phases.models import (
    PhaseValidationContext,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)
from flareward.elements.agents.phases.phase_definition import (
    PhaseDefinition,
    PhaseSystem,
    PhaseValidator,
)
from flareward.elements.agents.phases.phase_protocols import (
    PhaseContextProvider,
    PhaseState,
    PhaseToolProvider,
    PhaseTransitionPolicy,
    create_phase_state,
)
from flareward.elements.agents.phases.simple_phase_provider import (
    PhaseProvider as SimplePhaseProvider,
)

# Phase providers
from flareward.elements.agents.phases.unified_phase_provider import BasePhaseProvider, PhaseProvider

# Re-export WorkPlanStatus from workload layer (single source of truth)
from flareward.elements.workloads.domain import WorkPlanStatus

__all__ = [
    # Core models
    "ValidationSeverity",
    "ValidationIssue",
    "ValidationResult",
    "PhaseValidationContext",
    # Phase definitions
    "PhaseValidator",
    "PhaseDefinition",
    "PhaseSystem",
    # Phase protocols
    "PhaseState",
    "WorkPlanStatus",  # Re-exported from workload layer
    "PhaseContextProvider",
    "PhaseToolProvider",
    "PhaseTransitionPolicy",
    "create_phase_state",
    # Phase providers
    "PhaseProvider",
    "BasePhaseProvider",
    "SimplePhaseProvider",
    "PhaseRegistry",
    "ExtensiblePhaseProvider",
    "FlexiblePhaseProvider",
    # Utility modules
    "phase_guidance",
    "phase_tools",
]
