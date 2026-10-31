"""Base parser interface and common functionality."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Protocol, runtime_checkable

from mas.application.agents.constants import ParserDefaults, SpecialToolNames
from mas.application.agents.errors import ParseError, ParseErrorType, RecoveryStrategy
from mas.domain.agents import AgentAction, AgentFinish
from mas.domain.messages import ChatMessage, Role


@dataclass
class ParserConfig:
    """Base configuration for parsers."""

    recovery_strategy: RecoveryStrategy = RecoveryStrategy.REFLECTION
    error_action_tool: str = SpecialToolNames.PARSE_ERROR.value
    min_content_length: int = ParserDefaults.MIN_CONTENT_LENGTH
    max_content_length: int = ParserDefaults.MAX_CONTENT_LENGTH
    validate_schema: bool = ParserDefaults.VALIDATE_SCHEMA
    custom_settings: dict[str, Any] = None

    def __post_init__(self):
        if self.custom_settings is None:
            self.custom_settings = {}


@runtime_checkable
class OutputParser(Protocol):
    """Protocol defining the interface for all output parsers."""

    def parse(self, message: ChatMessage) -> list[AgentAction] | AgentFinish:
        """Parse assistant message into actions or finish."""
        ...

    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """Convert parse error into recovery action."""
        ...

    def validate_message(self, message: ChatMessage) -> None:
        """Validate message format before parsing."""
        ...


class BaseOutputParser(ABC):
    """Abstract base class for output parsers with common functionality."""

    def __init__(self, config: ParserConfig | None = None):
        """Initialize parser with configuration."""
        self.config = config or ParserConfig()

    def validate_message(self, message: ChatMessage) -> None:
        """Common message validation logic."""
        if not isinstance(message, ChatMessage):
            raise ParseError(
                f"Expected ChatMessage, got {type(message)}",
                ParseErrorType.INVALID_FORMAT,
                str(message),
                recoverable=False,
            )

        if message.role != Role.ASSISTANT:
            raise ParseError(
                f"Expected ASSISTANT role, got {message.role}",
                ParseErrorType.INVALID_ROLE,
                message.content or "",
                recoverable=False,
            )

        content = message.content or ""
        if len(content) < self.config.min_content_length and not hasattr(message, "tool_calls"):
            raise ParseError(
                f"Message content too short ({len(content)} chars, "
                f"min {self.config.min_content_length})",
                ParseErrorType.MISSING_CONTENT,
                content,
                recoverable=True,
                recovery_strategy=self.config.recovery_strategy,
            )

        if len(content) > self.config.max_content_length:
            raise ParseError(
                f"Message content too long ({len(content)} chars, "
                f"max {self.config.max_content_length})",
                ParseErrorType.VALIDATION_ERROR,
                content[:1000] + "...",  # Truncate for error message
                recoverable=True,
            )

    @abstractmethod
    def parse(self, message: ChatMessage) -> list[AgentAction] | AgentFinish:
        """Abstract parse method - must be implemented by subclasses."""
        ...

    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """Default error recovery implementation."""
        tool_name = self._get_recovery_tool_name(error)
        tool_input = self._build_recovery_input(error)

        return AgentAction(
            tool=tool_name,
            tool_input=tool_input,
            reasoning=f"Recovering from {error.error_type.value}: {error}",
            raw_output=error.raw_output,
            status=error.error_type.name.lower(),
            error=str(error),
        )

    def _get_recovery_tool_name(self, error: ParseError) -> str:
        """Determine recovery tool name based on error type."""
        if error.recovery_strategy == RecoveryStrategy.REFLECTION:
            return self.config.error_action_tool
        elif error.recovery_strategy == RecoveryStrategy.ERROR_ACTION:
            return f"_handle_{error.error_type.value}"
        else:
            return "_generic_error"

    def _build_recovery_input(self, error: ParseError) -> dict[str, Any]:
        """Build tool input for recovery action."""
        base_input = {
            "error": str(error),
            "error_type": error.error_type.value,
            "raw_output": error.raw_output,
            "recoverable": error.recoverable,
        }

        # Add error-specific context
        if error.error_type == ParseErrorType.TOOL_CALL_ERROR:
            base_input.update(
                {
                    "expected": "valid tool calls with proper names and arguments",
                    "guidance": (
                        "Ensure tool calls have valid names and properly formatted arguments"
                    ),
                }
            )
        elif error.error_type == ParseErrorType.JSON_ERROR:
            base_input.update(
                {
                    "expected": "valid JSON format",
                    "guidance": "Check JSON syntax, quotes, and brackets",
                }
            )
        elif error.error_type == ParseErrorType.INVALID_FORMAT:
            base_input.update(
                {
                    "expected": "recognized output format",
                    "guidance": "Follow the specified output format exactly",
                }
            )

        # Add custom context
        base_input.update(error.context)

        return base_input

    def _create_safe_action(
        self,
        tool: str,
        tool_input: dict[str, Any],
        reasoning: str = "",
        error: str | None = None,
        id: str | None = None,
    ) -> AgentAction:
        """Helper to create AgentAction with safe defaults."""
        action_kwargs = {
            "tool": tool,
            "tool_input": tool_input,
            "reasoning": reasoning or f"Using {tool}",
            "error": error,
        }

        if id is not None:
            action_kwargs["id"] = id

        return AgentAction(**action_kwargs)

    def _create_safe_finish(
        self, output: str, reasoning: str = "", return_values: dict[str, Any] | None = None
    ) -> AgentFinish:
        """Helper to create AgentFinish with safe defaults."""
        return AgentFinish(
            output=output,
            reasoning=reasoning or "Providing final answer",
            return_values=return_values or {},
        )
