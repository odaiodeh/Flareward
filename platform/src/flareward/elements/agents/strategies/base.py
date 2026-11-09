"""Base agent strategy interface and utilities."""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from flareward.elements.agents.constants import StrategyDefaults
from flareward.elements.agents.domain.models import AgentObservation, AgentStep, StepType
from flareward.elements.agents.parsers import OutputParser, ParseError
from flareward.elements.messaging.domain.messages import ChatMessage
from flareward.elements.ports.tool import BaseTool


class AgentStrategy(ABC):
    """Abstract base class for agent planning strategies."""

    @property
    @abstractmethod
    def strategy_name(self) -> str:
        """Return the name/type of this strategy for identification."""
        pass

    def __init__(
        self,
        *,
        llm_chat: Callable[[list[ChatMessage], list[BaseTool]], Awaitable[ChatMessage]],
        tools: list[BaseTool],
        parser: OutputParser,
        max_steps: int = StrategyDefaults.MAX_STEPS,
        system_message: str | None = None,
    ):
        """Initialize base strategy."""
        self.llm_chat = llm_chat
        self.all_tools = {tool.name: tool for tool in tools}
        self.parser = parser
        self.max_steps = max_steps
        self.system_message = system_message
        self._step_count = 0
        self._error_count = 0

    @abstractmethod
    def get_tools_for_phase(self, phase: str, context: dict[str, Any] = None) -> list[BaseTool]:
        """Get tools to expose to LLM for current phase."""
        ...

    @abstractmethod
    async def think(self, messages: list[ChatMessage]) -> list[AgentStep]:
        """Generate next steps based on current state."""
        ...

    @abstractmethod
    def should_continue(self, history: list[AgentStep]) -> bool:
        """Check if strategy should continue execution."""
        ...

    def format_observations(self, observations: list[AgentObservation]) -> str:
        """Format observation history for LLM context."""
        if not observations:
            return ""

        formatted = []
        for i, obs in enumerate(observations, 1):
            entry = [f"Step {i}:"]
            entry.append(f"Tool: {obs.tool}")

            if obs.success:
                entry.append(f"Result: {obs.output}")
            else:
                entry.append(f"Error: {obs.error}")

            entry.append(f"Execution time: {obs.execution_time:.3f}s")
            formatted.append("\n".join(entry))

        return "\n\n".join(formatted)

    @abstractmethod
    def build_context(self, messages: list[ChatMessage]) -> list[ChatMessage]:
        """Build complete context for LLM from conversation history."""
        ...

    def handle_parse_error(self, error: ParseError) -> list[AgentStep]:
        """Handle LLM output parsing errors."""
        self._error_count += 1

        # Create terminal error step
        return [
            AgentStep(
                StepType.ERROR,
                error,
                metadata={
                    "error_type": "parse_error",
                    "error_count": self._error_count,
                    "recoverable": getattr(error, "recoverable", False),
                },
            )
        ]

    def increment_step_count(self) -> None:
        """Increment internal step counter."""
        self._step_count += 1

    def reset_counters(self) -> None:
        """Reset internal counters (useful for reusing strategy instances)."""
        self._step_count = 0
        self._error_count = 0

    @property
    def step_count(self) -> int:
        """Current step count."""
        return self._step_count

    @property
    def error_count(self) -> int:
        """Current error count."""
        return self._error_count
