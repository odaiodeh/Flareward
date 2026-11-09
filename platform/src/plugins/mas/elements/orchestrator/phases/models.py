"""
Orchestrator-specific phase models.

Contains Pydantic models for orchestrator phase configuration and state management.
"""

from typing import Dict

from pydantic import BaseModel, Field


class PhaseIterationLimits(BaseModel):
    """
    Configuration for phase iteration limits.

    SOLID SRP: Single responsibility for managing phase iteration configuration.
    Uses Pydantic for validation and clean configuration management.
    """

    planning: int = Field(default=10, ge=1, description="Maximum iterations for planning phase")
    allocation: int = Field(default=10, ge=1, description="Maximum iterations for allocation phase")
    execution: int = Field(default=10, ge=1, description="Maximum iterations for execution phase")
    monitoring: int = Field(default=10, ge=1, description="Maximum iterations for monitoring phase")
    synthesis: int = Field(default=10, ge=1, description="Maximum iterations for synthesis phase")

    def get_limit(self, phase_name: str) -> int:
        """
        Get iteration limit for a specific phase.

        Args:
            phase_name: Name of the phase

        Returns:
            Iteration limit for the phase, default 10 if unknown
        """
        return getattr(self, phase_name, 10)

    def to_dict(self) -> Dict[str, int]:
        return self.model_dump()


class PhaseIterationState(BaseModel):
    """
    State tracking for phase iterations.

    SOLID SRP: Single responsibility for tracking current phase iteration state.
    Immutable design with proper state management.
    """

    planning: int = Field(default=0, ge=0, description="Current planning phase iterations")
    allocation: int = Field(default=0, ge=0, description="Current allocation phase iterations")
    execution: int = Field(default=0, ge=0, description="Current execution phase iterations")
    monitoring: int = Field(default=0, ge=0, description="Current monitoring phase iterations")
    synthesis: int = Field(default=0, ge=0, description="Current synthesis phase iterations")

    def get_count(self, phase_name: str) -> int:
        """
        Get current iteration count for a specific phase.

        Args:
            phase_name: Name of the phase

        Returns:
            Current iteration count for the phase, 0 if unknown
        """
        return getattr(self, phase_name, 0)

    def increment(self, phase_name: str) -> "PhaseIterationState":
        """
        Create new state with incremented count for the given phase.

        Immutable pattern: Returns new instance instead of modifying current one.

        Args:
            phase_name: Name of the phase to increment

        Returns:
            New PhaseIterationState with incremented count
        """
        current_values = self.model_dump()
        if phase_name in current_values:
            current_values[phase_name] += 1
        return PhaseIterationState(**current_values)

    def reset(self, phase_name: str) -> "PhaseIterationState":
        """
        Create new state with reset count for the given phase.

        Args:
            phase_name: Name of the phase to reset

        Returns:
            New PhaseIterationState with reset count
        """
        current_values = self.model_dump()
        if phase_name in current_values:
            current_values[phase_name] = 0
        return PhaseIterationState(**current_values)

    def is_exceeded(self, phase_name: str, limits: PhaseIterationLimits) -> bool:
        """
        Check if iteration limit is exceeded for the given phase.

        Args:
            phase_name: Name of the phase to check
            limits: Phase iteration limits configuration

        Returns:
            True if limit exceeded, False otherwise
        """
        current_count = self.get_count(phase_name)
        limit = limits.get_limit(phase_name)
        return current_count >= limit
