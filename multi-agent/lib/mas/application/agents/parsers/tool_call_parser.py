"""Tool call parser for ChatMessage.tool_calls format."""

from dataclasses import dataclass
from typing import Any

from mas.application.agents.constants import ParserDefaults, SpecialToolNames, ToolExecutionDefaults
from mas.application.agents.parsers.base import (
    BaseOutputParser,
    ParseError,
    ParseErrorType,
    ParserConfig,
)
from mas.domain.agents import AgentAction, AgentFinish
from mas.domain.messages import ChatMessage


@dataclass
class ToolCallParserConfig(ParserConfig):
    """Configuration specific to tool call parser."""

    require_tool_call_id: bool = ToolExecutionDefaults.REQUIRE_TOOL_CALL_ID
    validate_tool_args: bool = ToolExecutionDefaults.VALIDATE_ARGS
    allow_empty_args: bool = ToolExecutionDefaults.ALLOW_EMPTY_ARGS
    max_tool_calls_per_message: int = ToolExecutionDefaults.MAX_TOOL_CALLS_PER_MESSAGE
    fallback_to_content: bool = ParserDefaults.FALLBACK_TO_CONTENT


class ToolCallParser(BaseOutputParser):
    """Parser for ChatMessage.tool_calls format."""

    def __init__(self, config: ToolCallParserConfig | None = None):
        """Initialize tool call parser."""
        self.config = config or ToolCallParserConfig()
        super().__init__(self.config)

    def parse(self, message: ChatMessage) -> list[AgentAction] | AgentFinish:
        """Parse ChatMessage into actions or finish."""
        try:
            # Basic message validation
            self.validate_message(message)

            # Check for tool calls
            if hasattr(message, "tool_calls") and message.tool_calls:
                return self._parse_tool_calls(message)
            else:
                return self._parse_as_finish(message)

        except ParseError:
            # Re-raise parse errors as-is
            raise
        except Exception as e:
            # Convert unexpected errors to ParseError
            raise ParseError(
                f"Unexpected parsing error: {e}",
                ParseErrorType.MALFORMED_STRUCTURE,
                message.content or "",
                recoverable=True,
                context={"original_error": str(e)},
            ) from e

    def _parse_tool_calls(self, message: ChatMessage) -> list[AgentAction]:
        """Parse tool calls into AgentActions."""
        tool_calls = message.tool_calls

        # Validate tool call count
        if len(tool_calls) > self.config.max_tool_calls_per_message:
            raise ParseError(
                f"Too many tool calls ({len(tool_calls)}, "
                f"max {self.config.max_tool_calls_per_message})",
                ParseErrorType.VALIDATION_ERROR,
                message.content or "",
                recoverable=True,
            )

        actions = []
        for i, tc in enumerate(tool_calls):
            try:
                action = self._parse_single_tool_call(tc, message, i)
                actions.append(action)
            except Exception as e:
                raise ParseError(
                    f"Invalid tool call #{i}: {e}",
                    ParseErrorType.TOOL_CALL_ERROR,
                    message.content or "",
                    recoverable=True,
                    context={
                        "tool_call_index": i,
                        "tool_name": getattr(tc, "name", "unknown"),
                        "original_error": str(e),
                    },
                ) from e

        if not actions:
            raise ParseError(
                "No valid tool calls found",
                ParseErrorType.TOOL_CALL_ERROR,
                message.content or "",
                recoverable=True,
            )

        return actions

    def _parse_single_tool_call(self, tool_call, message: ChatMessage, index: int) -> AgentAction:
        """Parse a single tool call into AgentAction."""
        # Validate tool name
        if not hasattr(tool_call, "name") or not tool_call.name:
            raise ValueError("Tool call missing name")

        if not isinstance(tool_call.name, str):
            raise ValueError(f"Tool name must be string, got {type(tool_call.name)}")

        # Validate tool call ID if required
        if self.config.require_tool_call_id:
            if not hasattr(tool_call, "tool_call_id") or not tool_call.tool_call_id:
                raise ValueError("Tool call missing required ID")

        # Get arguments
        args = {}
        if hasattr(tool_call, "args"):
            args = tool_call.args or {}
            if not isinstance(args, dict):
                raise ValueError(f"Tool args must be dict, got {type(args)}")
        elif not self.config.allow_empty_args:
            raise ValueError("Tool call missing arguments")

        # Validate arguments if enabled
        if self.config.validate_tool_args and args:
            self._validate_tool_arguments(args, tool_call.name)

        # Create action with original tool_call_id
        return self._create_safe_action(
            tool=tool_call.name,
            tool_input=args,
            reasoning=message.content or f"Using {tool_call.name}",
            id=tool_call.tool_call_id,  # Use original tool_call_id
        )

    def _parse_as_finish(self, message: ChatMessage) -> AgentFinish:
        """Parse message without tool calls as final answer."""
        content = message.content or ""

        if not content.strip():
            if self.config.fallback_to_content:
                # Create empty finish if allowed
                return self._create_safe_finish(output="", reasoning="Empty response from LLM")
            else:
                raise ParseError(
                    "Message has no content and no tool calls",
                    ParseErrorType.MISSING_CONTENT,
                    content,
                    recoverable=True,
                )

        return self._create_safe_finish(
            output=content.strip(), reasoning="No tool calls - providing final answer"
        )

    def _validate_tool_arguments(self, args: dict[str, Any], tool_name: str) -> None:
        """Validate tool arguments structure."""
        # Basic validation - can be extended
        if not isinstance(args, dict):
            raise ValueError(f"Arguments must be dictionary for tool {tool_name}")

        # Check for obviously invalid values
        for key, value in args.items():
            if not isinstance(key, str):
                raise ValueError(f"Argument keys must be strings, got {type(key)} for {tool_name}")

            # Check for problematic values
            if value is None and key in ["query", "input", "text"]:  # Common required fields
                raise ValueError(f"Required argument '{key}' cannot be null for {tool_name}")

    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """Create recovery action for tool call parsing errors."""
        # Create specific recovery based on error type
        if error.error_type == ParseErrorType.TOOL_CALL_ERROR:
            return self._create_tool_call_recovery_action(error)
        elif error.error_type == ParseErrorType.MISSING_CONTENT:
            return self._create_content_recovery_action(error)
        else:
            # Use base implementation for other errors
            return super().parse_error_recovery(error)

    def _create_tool_call_recovery_action(self, error: ParseError) -> AgentAction:
        """Create specific recovery for tool call errors."""
        return self._create_safe_action(
            tool=SpecialToolNames.TOOL_CALL_ERROR.value,
            tool_input={
                "error": str(error),
                "context": error.context,
                "guidance": (
                    "Tool calls must have valid names and properly formatted arguments. "
                    "Ensure all required fields are present and arguments are correct types."
                ),
                "example": {
                    "correct_format": (
                        "Use function calls with proper tool names and dict arguments"
                    ),
                    "common_issues": ["Missing tool name", "Invalid arguments", "Wrong data types"],
                },
            },
            reasoning="Reflecting on tool call formatting error",
            error=str(error),
        )

    def _create_content_recovery_action(self, error: ParseError) -> AgentAction:
        """Create specific recovery for missing content errors."""
        return self._create_safe_action(
            tool=SpecialToolNames.MISSING_CONTENT.value,
            tool_input={
                "error": str(error),
                "guidance": (
                    "Responses should either contain tool calls for actions or "
                    "text content for final answers. Empty responses are not helpful."
                ),
                "suggestion": "Provide either a tool call or a meaningful text response",
            },
            reasoning="Reflecting on missing content error",
            error=str(error),
        )
