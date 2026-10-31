"""Phase guidance provider for agent strategies."""

from mas.application.agents.constants import ExecutionPhase


class PhaseGuidanceProvider:
    """Provides phase-specific guidance for LLM context."""

    # Phase-specific guidance (kept minimal to avoid token bloat)
    _PHASE_GUIDANCE: dict[ExecutionPhase, str] = {
        ExecutionPhase.PLANNING: (
            "PHASE: PLANNING - Create detailed work plan with dependencies. "
            "Break down tasks logically. Don't execute or delegate yet."
        ),
        ExecutionPhase.ALLOCATION: (
            "PHASE: ALLOCATION - Assign work items to appropriate nodes. "
            "Use adjacency info to delegate. Don't execute local work yet."
        ),
        ExecutionPhase.EXECUTION: (
            "PHASE: EXECUTION - Execute local work items only. "
            "Don't modify plan structure or delegate new work."
        ),
        ExecutionPhase.MONITORING: (
            "PHASE: MONITORING - Interpret responses and decide next steps. "
            "Respect retry limits (check item.retry_count vs max_retries). "
            "Mark status only when certain about outcome."
        ),
        ExecutionPhase.SYNTHESIS: (
            "PHASE: SYNTHESIS - Summarize completed work and produce final deliverables. "
            "Focus on results and outputs."
        ),
    }

    @classmethod
    def get_guidance(cls, phase: ExecutionPhase) -> str:
        """Get concise guidance for the specified phase."""
        return cls._PHASE_GUIDANCE.get(phase, "")

    @classmethod
    def get_all_phases(cls) -> dict[ExecutionPhase, str]:
        """Get all available phase guidance (for testing/documentation)."""
        return cls._PHASE_GUIDANCE.copy()
