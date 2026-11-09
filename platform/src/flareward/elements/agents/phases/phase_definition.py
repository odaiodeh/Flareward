"""Clean Pydantic models for phase definitions."""

import logging

# Import for typing - avoid circular imports
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import BaseModel, Field

from flareward.elements.ports.tool import BaseTool

if TYPE_CHECKING:
    from flareward.elements.agents.phases.models import PhaseValidationContext

logger = logging.getLogger(__name__)


class PhaseValidator(Protocol):
    """Protocol for phase-specific validators."""

    def validate(self, context: PhaseValidationContext) -> str:
        """Validate phase state and return guidance text."""
        ...


class PhaseDefinition(BaseModel):
    """Clean definition of a single execution phase."""

    name: str = Field(..., description="Phase name (e.g., 'planning', 'execution')")
    description: str = Field(..., description="What this phase does")
    tools: list[BaseTool] = Field(
        default_factory=list, description="Actual tool objects for this phase"
    )
    guidance: str = Field(..., description="LLM guidance for this phase")
    validators: list[Any] = Field(default_factory=list, description="Validators for this phase")
    max_iterations: int = Field(default=10, ge=1, description="Maximum iterations for this phase")

    class Config:
        arbitrary_types_allowed = True  # Allow BaseTool objects and validators

    def add_tool(self, tool: BaseTool) -> None:
        """Add a tool to this phase."""
        if tool not in self.tools:
            self.tools.append(tool)

    def add_tools(self, tools: list[BaseTool]) -> None:
        """Add multiple tools to this phase."""
        for tool in tools:
            self.add_tool(tool)

    def add_validator(self, validator: PhaseValidator) -> None:
        """Add a validator to this phase."""
        # Runtime type check since Pydantic can't validate Protocol types
        if not hasattr(validator, "validate") or not callable(getattr(validator, "validate")):
            raise ValueError(
                "Validator must implement PhaseValidator protocol with validate() method"
            )
        self.validators.append(validator)

    def run_validators(self, context: PhaseValidationContext) -> str:
        """Run all validators for this phase and return combined guidance."""
        guidance_parts: list[str] = []

        for validator in self.validators:
            try:
                guidance = validator.validate(context)
                if guidance:
                    guidance_parts.append(guidance)
            except Exception as e:
                logger.warning(
                    "phase.validate_error",
                    extra={"phase": self.name, "error": str(e), "detail": "validator"},
                )
                # Continue with other validators

        return "\n\n".join(guidance_parts) if guidance_parts else ""

    def get_tool_names(self) -> list[str]:
        """Get list of tool names for debugging/logging."""
        return [tool.name for tool in self.tools]


class PhaseSystem(BaseModel):
    """Complete phase system definition."""

    name: str = Field(..., description="Name of this phase system (e.g., 'orchestrator')")
    description: str = Field(..., description="What this phase system does")
    phases: list[PhaseDefinition] = Field(
        default_factory=list, description="All phases in execution order"
    )

    def add_phase(self, phase: PhaseDefinition) -> None:
        """Add a phase to this system."""
        self.phases.append(phase)

    def get_phase(self, name: str) -> PhaseDefinition | None:
        """Get a phase by name."""
        for phase in self.phases:
            if phase.name == name:
                return phase
        return None

    def get_phase_names(self) -> list[str]:
        """Get list of all phase names in order."""
        return [phase.name for phase in self.phases]

    def get_tools_for_phase(self, phase_name: str) -> list[BaseTool]:
        """Get actual tool objects for a specific phase."""
        phase = self.get_phase(phase_name)
        return phase.tools if phase else []

    def get_guidance_for_phase(self, phase_name: str) -> str:
        """Get guidance text for a specific phase."""
        phase = self.get_phase(phase_name)
        return phase.guidance if phase else ""
