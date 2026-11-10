"""Text parser for structured text formats."""

import json
import re
from dataclasses import dataclass
from enum import Enum
from re import Pattern
from typing import Any

from lumora.elements.agents.domain.models import AgentAction, AgentFinish
from lumora.elements.agents.parsers.base import (
    BaseOutputParser,
    ParseError,
    ParseErrorType,
    ParserConfig,
)
from lumora.elements.messaging.domain.messages import ChatMessage


class TextFormatType(Enum):
    """Supported text format types."""

    REACT = "react"  # Thought/Action/Action Input format
    SIMPLE = "simple"  # Direct Action: / Final Answer: format
    JSON_STRUCTURED = "json"  # JSON with action/finish fields
    CUSTOM = "custom"  # Custom regex patterns


@dataclass
class TextPatterns:
    """Regex patterns for parsing different text formats."""

    thought_pattern: Pattern | None = None
    action_pattern: Pattern = None
    action_input_pattern: Pattern = None
    final_answer_pattern: Pattern = None

    def __post_init__(self):
        # Compile patterns if they're strings
        for field_name in [
            "thought_pattern",
            "action_pattern",
            "action_input_pattern",
            "final_answer_pattern",
        ]:
            pattern = getattr(self, field_name)
            if isinstance(pattern, str):
                setattr(self, field_name, re.compile(pattern, re.IGNORECASE | re.MULTILINE))


@dataclass
class TextParserConfig(ParserConfig):
    """Configuration for text parser."""

    format_type: TextFormatType = TextFormatType.REACT
    custom_patterns: TextPatterns | None = None
    require_thought: bool = False
    min_thought_length: int = 10
    allow_multiple_actions: bool = False
    strict_format: bool = False
    case_sensitive: bool = False


class TextParser(BaseOutputParser):
    """Parser for structured text formats."""

    # Predefined patterns for common formats
    REACT_PATTERNS = TextPatterns(
        thought_pattern=re.compile(
            r"Thought:\s*(.+?)(?=\n(?:Action|Final Answer))",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        ),
        action_pattern=re.compile(r"Action:\s*(.+?)(?=\n)", re.IGNORECASE),
        action_input_pattern=re.compile(
            r"Action Input:\s*(.+?)(?=\n(?:Observation|Thought|Action|Final Answer|$))",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        ),
        final_answer_pattern=re.compile(
            r"Final Answer:\s*(.+?)(?=\n(?:Thought|Action|$)|$)",
            re.IGNORECASE | re.MULTILINE | re.DOTALL,
        ),
    )

    SIMPLE_PATTERNS = TextPatterns(
        action_pattern=re.compile(r"Action:\s*(.+?)(?=\n)", re.IGNORECASE),
        action_input_pattern=re.compile(
            r"Input:\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE | re.DOTALL
        ),
        final_answer_pattern=re.compile(
            r"(?:Final Answer|Answer):\s*(.+?)(?=\n|$)", re.IGNORECASE | re.MULTILINE | re.DOTALL
        ),
    )

    def __init__(self, config: TextParserConfig | None = None):
        """Initialize text parser."""
        self.config = config or TextParserConfig()
        super().__init__(self.config)

        # Set up patterns based on format type
        self.patterns = self._get_patterns_for_format(self.config.format_type)

    def _get_patterns_for_format(self, format_type: TextFormatType) -> TextPatterns:
        """Get regex patterns for the specified format type."""
        if format_type == TextFormatType.REACT:
            return self.REACT_PATTERNS
        elif format_type == TextFormatType.SIMPLE:
            return self.SIMPLE_PATTERNS
        elif format_type == TextFormatType.CUSTOM and self.config.custom_patterns:
            return self.config.custom_patterns
        else:
            # Default to ReAct patterns
            return self.REACT_PATTERNS

    def parse(self, message: ChatMessage) -> list[AgentAction] | AgentFinish:
        """Parse structured text message into actions or finish."""
        try:
            # Basic validation
            self.validate_message(message)

            content = message.content or ""
            if not content.strip():
                raise ParseError(
                    "Empty message content",
                    ParseErrorType.MISSING_CONTENT,
                    content,
                    recoverable=True,
                )

            # Try to parse as different formats based on configuration
            if self.config.format_type == TextFormatType.JSON_STRUCTURED:
                return self._parse_json_format(content)
            else:
                return self._parse_text_format(content)

        except ParseError:
            # Re-raise parse errors
            raise
        except Exception as e:
            raise ParseError(
                f"Unexpected text parsing error: {e}",
                ParseErrorType.MALFORMED_STRUCTURE,
                message.content or "",
                recoverable=True,
                context={"original_error": str(e)},
            ) from e

    def _parse_json_format(self, content: str) -> list[AgentAction] | AgentFinish:
        """Parse JSON-structured format."""
        try:
            data = json.loads(content.strip())
        except json.JSONDecodeError as e:
            raise ParseError(
                f"Invalid JSON format: {e}",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"json_error": str(e)},
            ) from e

        if not isinstance(data, dict):
            raise ParseError(
                "JSON must be an object", ParseErrorType.JSON_ERROR, content, recoverable=True
            )

        response_type = data.get("type", "").lower()

        if response_type == "action":
            return self._parse_json_action(data, content)
        elif response_type == "finish":
            return self._parse_json_finish(data, content)
        else:
            raise ParseError(
                f"Unknown JSON response type: {response_type}",
                ParseErrorType.UNKNOWN_FORMAT,
                content,
                recoverable=True,
                context={"response_type": response_type},
            )

    def _parse_json_action(self, data: dict[str, Any], content: str) -> list[AgentAction]:
        """Parse JSON action format."""
        if "action" not in data:
            raise ParseError(
                "JSON action missing 'action' field",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
            )

        action = self._create_safe_action(
            tool=data["action"], tool_input=data.get("input", {}), reasoning=data.get("thought", "")
        )

        return [action]

    def _parse_json_finish(self, data: dict[str, Any], content: str) -> AgentFinish:
        """Parse JSON finish format."""
        if "output" not in data:
            raise ParseError(
                "JSON finish missing 'output' field",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
            )

        return self._create_safe_finish(output=data["output"], reasoning=data.get("thought", ""))

    def _parse_text_format(self, content: str) -> list[AgentAction] | AgentFinish:
        """Parse text-based formats using regex patterns."""
        # Check for final answer first
        if self.patterns.final_answer_pattern:
            final_match = self.patterns.final_answer_pattern.search(content)
            if final_match:
                return self._parse_final_answer(final_match, content)

        # Check for actions
        if self.patterns.action_pattern:
            action_matches = list(self.patterns.action_pattern.finditer(content))
            if action_matches:
                return self._parse_actions(action_matches, content)

        # If no patterns match, try to determine intent
        return self._parse_fallback_format(content)

    def _parse_final_answer(self, match: re.Match, content: str) -> AgentFinish:
        """Parse final answer from regex match."""
        answer = match.group(1).strip()

        # Extract thought if available
        thought = ""
        if self.patterns.thought_pattern:
            thought_match = self.patterns.thought_pattern.search(content)
            if thought_match:
                thought = thought_match.group(1).strip()

        return self._create_safe_finish(
            output=answer, reasoning=thought or "Extracted from final answer pattern"
        )

    def _parse_actions(self, action_matches: list[re.Match], content: str) -> list[AgentAction]:
        """Parse actions from regex matches."""
        actions = []

        for i, action_match in enumerate(action_matches):
            if not self.config.allow_multiple_actions and i > 0:
                break

            action_name = action_match.group(1).strip()
            if not action_name:
                continue

            # Find corresponding action input
            action_input = self._find_action_input_for_action(action_match, content)

            # Extract thought if available
            thought = self._find_thought_for_action(action_match, content)

            # Validate thought if required
            if self.config.require_thought and not thought:
                raise ParseError(
                    f"Thought required but not found for action: {action_name}",
                    ParseErrorType.MISSING_CONTENT,
                    content,
                    recoverable=True,
                    context={"action_name": action_name},
                )

            if self.config.require_thought and len(thought) < self.config.min_thought_length:
                raise ParseError(
                    f"Thought too short for action {action_name} "
                    f"({len(thought)} chars, min {self.config.min_thought_length})",
                    ParseErrorType.VALIDATION_ERROR,
                    content,
                    recoverable=True,
                    context={"action_name": action_name, "thought": thought},
                )

            action = self._create_safe_action(
                tool=action_name,
                tool_input=action_input,
                reasoning=thought or f"Using {action_name}",
            )

            actions.append(action)

        if not actions:
            raise ParseError(
                "No valid actions found in text",
                ParseErrorType.UNKNOWN_FORMAT,
                content,
                recoverable=True,
            )

        return actions

    def _find_action_input_for_action(self, action_match: re.Match, content: str) -> dict[str, Any]:
        """Find action input corresponding to an action."""
        if not self.patterns.action_input_pattern:
            return {}

        # Look for action input after this action
        search_start = action_match.end()
        remaining_content = content[search_start:]

        input_match = self.patterns.action_input_pattern.search(remaining_content)
        if not input_match:
            return {}

        input_text = input_match.group(1).strip()

        # Try to parse as JSON first
        try:
            return json.loads(input_text)
        except json.JSONDecodeError:
            # Fall back to simple key-value parsing or string input
            if ":" in input_text:
                # Try simple key:value parsing
                return self._parse_simple_key_value(input_text)
            else:
                # Use as single input parameter
                return {"input": input_text}

    def _find_thought_for_action(self, action_match: re.Match, content: str) -> str:
        """Find thought corresponding to an action."""
        if not self.patterns.thought_pattern:
            return ""

        # Look for thought before this action
        search_end = action_match.start()
        preceding_content = content[:search_end]

        # Find the last thought before this action
        thought_matches = list(self.patterns.thought_pattern.finditer(preceding_content))
        if thought_matches:
            return thought_matches[-1].group(1).strip()

        return ""

    def _parse_simple_key_value(self, text: str) -> dict[str, Any]:
        """Parse simple key:value format."""
        result = {}
        lines = text.split("\n")

        for line in lines:
            line = line.strip()
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.strip()
                value = value.strip()

                # Try to parse value as JSON
                try:
                    result[key] = json.loads(value)
                except json.JSONDecodeError:
                    result[key] = value

        return result or {"input": text}

    def _parse_fallback_format(self, content: str) -> AgentFinish:
        """Fallback parsing when no patterns match."""
        if self.config.strict_format:
            raise ParseError(
                "Content doesn't match expected format",
                ParseErrorType.UNKNOWN_FORMAT,
                content,
                recoverable=True,
            )

        # Use entire content as final answer
        return self._create_safe_finish(
            output=content.strip(), reasoning="No format patterns matched - using entire content"
        )

    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """Create recovery action for text parsing errors."""
        format_guidance = self._get_format_guidance()

        return self._create_safe_action(
            tool="_text_format_error",
            tool_input={
                "error": str(error),
                "error_type": error.error_type.value,
                "expected_format": self.config.format_type.value,
                "guidance": format_guidance,
                "example": self._get_format_example(),
                "raw_output": error.raw_output,
            },
            reasoning=f"Reflecting on {self.config.format_type.value} format error",
            error=str(error),
        )

    def _get_format_guidance(self) -> str:
        """Get format-specific guidance."""
        if self.config.format_type == TextFormatType.REACT:
            return (
                "Use the ReAct format: "
                "Thought: [your reasoning]\n"
                "Action: [tool_name]\n"
                "Action Input: [json_input]\n"
                "OR\n"
                "Final Answer: [your answer]"
            )
        elif self.config.format_type == TextFormatType.SIMPLE:
            return (
                "Use simple format: "
                "Action: [tool_name]\n"
                "Input: [input_data]\n"
                "OR\n"
                "Final Answer: [your answer]"
            )
        elif self.config.format_type == TextFormatType.JSON_STRUCTURED:
            return (
                "Use JSON format: "
                '{"type": "action", "action": "tool_name", "input": {...}, "thought": "..."}\n'
                "OR\n"
                '{"type": "finish", "output": "final answer", "thought": "..."}'
            )
        else:
            return "Follow the expected text format exactly"

    def _get_format_example(self) -> dict[str, str]:
        """Get format-specific examples."""
        if self.config.format_type == TextFormatType.REACT:
            return {
                "action_example": (
                    "Thought: I need to calculate the result\n"
                    "Action: calculator\n"
                    'Action Input: {"expression": "5 + 3"}'
                ),
                "finish_example": "Final Answer: The result is 8",
            }
        elif self.config.format_type == TextFormatType.JSON_STRUCTURED:
            return {
                "action_example": (
                    '{"type": "action", "action": "calculator", "input": {"expression": "5 + 3"}}'
                ),
                "finish_example": '{"type": "finish", "output": "The result is 8"}',
            }
        else:
            return {
                "action_example": "Action: calculator\nInput: 5 + 3",
                "finish_example": "Final Answer: The result is 8",
            }
