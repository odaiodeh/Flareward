"""Core phase provider abstraction."""

import logging
from abc import ABC, abstractmethod

# Import for typing - avoid circular imports
from typing import TYPE_CHECKING, Any

from lumora.elements.agents.phases.phase_definition import PhaseSystem
from lumora.elements.agents.phases.phase_protocols import PhaseState
from lumora.elements.messaging.domain.messages import ChatMessage
from lumora.elements.ports.tool import BaseTool

if TYPE_CHECKING:
    from lumora.elements.agents.phases.models import PhaseValidationContext

logger = logging.getLogger(__name__)


class PhaseProvider(ABC):
    """Abstract base class for phase management."""

    def __init__(self, tools: list[BaseTool]):
        """Initialize with available tools."""
        self._tools = tools
        self._phase_system = self._create_phase_system()

    @abstractmethod
    def _create_phase_system(self) -> PhaseSystem:
        """Create the complete phase system for this provider."""
        pass

    def get_phase_system(self) -> PhaseSystem:
        """Get the complete phase system definition."""
        return self._phase_system

    def get_supported_phases(self) -> list[str]:
        """Get list of phase names supported by this provider."""
        return self._phase_system.get_phase_names()

    def get_tools_for_phase(self, phase_name: str) -> list[BaseTool]:
        """Get actual tool objects for the given phase."""
        return self._phase_system.get_tools_for_phase(phase_name)

    def get_phase_guidance(self, phase_name: str) -> str:
        """Get guidance text for the given phase."""
        return self._phase_system.get_guidance_for_phase(phase_name)

    @abstractmethod
    def _build_validation_context(self, phase_name: str) -> PhaseValidationContext:
        """Build validation context for the given phase."""
        pass

    def get_phase_validation(self, phase_name: str) -> str:
        """Get validation guidance for the given phase."""
        phase = self._phase_system.get_phase(phase_name)
        if not phase:
            return ""

        try:
            context = self._build_validation_context(phase_name)
            return phase.run_validators(context)
        except Exception as e:
            logger.warning("phase.validate_error", extra={"phase": phase_name, "error": str(e)})
            return ""

    def build_phase_prompt(self, phase_name: str) -> str:
        """Build complete phase prompt with base guidance and validation."""
        base_guidance = self.get_phase_guidance(phase_name)
        validation_guidance = self.get_phase_validation(phase_name)

        if validation_guidance:
            return f"{base_guidance}\n\n{validation_guidance}"
        return base_guidance

    def get_dynamic_context_messages(self, phase_name: str) -> list[ChatMessage]:
        """Get dynamic context messages that should be refreshed before each LLM call."""
        return []

    @abstractmethod
    def get_phase_context(self) -> PhaseState:
        """Get current phase context - must be implemented by subclasses."""
        pass

    @abstractmethod
    def decide_next_phase(
        self, current_phase: str, context: PhaseState, observations: list[Any]
    ) -> str:
        """Decide the next phase (single-step decision)."""
        pass

    @abstractmethod
    def update_phase(self, current_phase: str, observations: list[Any]) -> str:
        """Update phase and return the new phase."""
        pass

    @abstractmethod
    def can_finish_now(self, current_phase: str) -> bool:
        """Determine if the agent can finish execution now."""
        pass

    # =================================================================
    # CONCRETE METHODS - Shared implementation
    # =================================================================

    def get_initial_phase(self) -> str:
        """Get the initial/starting phase for this provider."""
        phases = self.get_supported_phases()
        if not phases:
            raise ValueError("Phase system has no phases")
        return phases[0]

    def is_terminal_phase(self, phase_name: str) -> bool:
        """Check if a phase is terminal (workflow ends here)."""
        context = self.get_phase_context()
        next_phase = self.decide_next_phase(phase_name, context, [])
        return next_phase == phase_name

    def requires_tools(self, phase_name: str) -> bool:
        """Check if phase requires tools to proceed."""
        # Terminal phases don't require tools
        if self.is_terminal_phase(phase_name):
            return False

        # Check if phase has tools
        tools = self.get_tools_for_phase(phase_name)
        return len(tools) > 0

    def get_next_phase_in_sequence(self, current_phase: str) -> str | None:
        """Get next phase in natural sequential order (for fallback)."""
        if self.is_terminal_phase(current_phase):
            return None

        phases = self.get_supported_phases()
        try:
            idx = phases.index(current_phase)
            if idx < len(phases) - 1:
                return phases[idx + 1]
        except ValueError:
            pass

        return None

    def validate_transition(self, from_phase: str, to_phase: str) -> bool:
        """Validate that a phase transition is allowed."""
        return True


# Backward compatibility alias
BasePhaseProvider = PhaseProvider
