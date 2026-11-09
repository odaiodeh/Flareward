"""JSON parser for structured JSON responses."""

import json
from dataclasses import dataclass
from enum import Enum
from typing import Any

from flareward.elements.agents.domain.models import AgentAction, AgentFinish
from flareward.elements.agents.parsers.base import (
    BaseOutputParser,
    ParseError,
    ParseErrorType,
    ParserConfig,
)
from flareward.elements.messaging.domain.messages import ChatMessage


class JsonSchemaType(Enum):
    """Supported JSON schema types."""

    OPENAI_FUNCTIONS = "openai_functions"  # OpenAI function calling format
    SIMPLE_ACTION = "simple_action"  # {action: str, input: dict}
    AGENT_FORMAT = "agent_format"  # {type: action/finish, ...}
    CUSTOM = "custom"  # Custom schema


@dataclass
class JsonParserConfig(ParserConfig):
    """Configuration for JSON parser."""

    schema_type: JsonSchemaType = JsonSchemaType.AGENT_FORMAT
    validate_schema: bool = True
    allow_multiple_functions: bool = True
    require_type_field: bool = True
    strict_validation: bool = False
    custom_schema: dict[str, Any] | None = None

    # Field mappings for different schemas
    action_field: str = "action"
    input_field: str = "input"
    type_field: str = "type"
    output_field: str = "output"
    reasoning_field: str = "reasoning"


class JsonParser(BaseOutputParser):
    """Parser for JSON-formatted responses."""

    def __init__(self, config: JsonParserConfig | None = None):
        """Initialize JSON parser."""
        self.config = config or JsonParserConfig()
        super().__init__(self.config)

    def parse(self, message: ChatMessage) -> list[AgentAction] | AgentFinish:
        """Parse JSON message into actions or finish."""
        try:
            # Basic validation
            self.validate_message(message)

            content = message.content or ""
            if not content.strip():
                raise ParseError(
                    "Empty JSON content", ParseErrorType.MISSING_CONTENT, content, recoverable=True
                )

            # Parse JSON
            try:
                json_data = json.loads(content.strip())
            except json.JSONDecodeError as e:
                raise ParseError(
                    f"Invalid JSON format: {e}",
                    ParseErrorType.JSON_ERROR,
                    content,
                    recoverable=True,
                    context={
                        "json_error": str(e),
                        "line": getattr(e, "lineno", None),
                        "column": getattr(e, "colno", None),
                    },
                ) from e

            # Parse based on schema type
            return self._parse_json_data(json_data, content)

        except ParseError:
            # Re-raise parse errors
            raise
        except Exception as e:
            raise ParseError(
                f"Unexpected JSON parsing error: {e}",
                ParseErrorType.MALFORMED_STRUCTURE,
                message.content or "",
                recoverable=True,
                context={"original_error": str(e)},
            ) from e

    def _parse_json_data(self, data: Any, content: str) -> list[AgentAction] | AgentFinish:
        """Parse JSON data based on configured schema type."""
        if self.config.schema_type == JsonSchemaType.OPENAI_FUNCTIONS:
            return self._parse_openai_format(data, content)
        elif self.config.schema_type == JsonSchemaType.SIMPLE_ACTION:
            return self._parse_simple_action_format(data, content)
        elif self.config.schema_type == JsonSchemaType.AGENT_FORMAT:
            return self._parse_agent_format(data, content)
        elif self.config.schema_type == JsonSchemaType.CUSTOM:
            return self._parse_custom_format(data, content)
        else:
            # Default to agent format
            return self._parse_agent_format(data, content)

    def _parse_openai_format(self, data: Any, content: str) -> list[AgentAction] | AgentFinish:
        """Parse OpenAI function calling format."""
        if isinstance(data, list):
            # List of function calls
            return self._parse_function_list(data, content)
        elif isinstance(data, dict):
            if "function_calls" in data:
                return self._parse_function_list(data["function_calls"], content)
            elif "name" in data and "arguments" in data:
                # Single function call
                return self._parse_function_list([data], content)
            elif "functions" in data:
                return self._parse_function_list(data["functions"], content)
            else:
                # Try to parse as agent format fallback
                return self._parse_agent_format(data, content)
        else:
            raise ParseError(
                "OpenAI format must be object or array",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"data_type": type(data).__name__},
            )

    def _parse_function_list(self, functions: list[dict], content: str) -> list[AgentAction]:
        """Parse list of function calls."""
        if not isinstance(functions, list):
            raise ParseError(
                "Function calls must be array", ParseErrorType.JSON_ERROR, content, recoverable=True
            )

        if not functions:
            raise ParseError(
                "Empty function calls array",
                ParseErrorType.MISSING_CONTENT,
                content,
                recoverable=True,
            )

        if len(functions) > 1 and not self.config.allow_multiple_functions:
            raise ParseError(
                f"Multiple functions not allowed ({len(functions)} found)",
                ParseErrorType.VALIDATION_ERROR,
                content,
                recoverable=True,
            )

        actions = []
        for i, func in enumerate(functions):
            try:
                action = self._parse_single_function(func, i)
                actions.append(action)
            except Exception as e:
                raise ParseError(
                    f"Invalid function #{i}: {e}",
                    ParseErrorType.JSON_ERROR,
                    content,
                    recoverable=True,
                    context={
                        "function_index": i,
                        "function_name": func.get("name", "unknown"),
                        "original_error": str(e),
                    },
                ) from e

        return actions

    def _parse_single_function(self, func: dict[str, Any], index: int) -> AgentAction:
        """Parse single function call."""
        if not isinstance(func, dict):
            raise ValueError(f"Function #{index} must be object")

        # Get function name
        if "name" not in func:
            raise ValueError("Function missing 'name' field")

        name = func["name"]
        if not isinstance(name, str) or not name.strip():
            raise ValueError("Function name must be non-empty string")

        # Get arguments
        arguments = func.get("arguments", {})
        if isinstance(arguments, str):
            # Sometimes arguments are JSON strings
            try:
                arguments = json.loads(arguments)
            except json.JSONDecodeError:
                raise ValueError(f"Invalid arguments JSON: {arguments}")

        if not isinstance(arguments, dict):
            raise ValueError("Function arguments must be object")

        return self._create_safe_action(
            tool=name, tool_input=arguments, reasoning=func.get("reasoning", f"Calling {name}")
        )

    def _parse_simple_action_format(self, data: Any, content: str) -> list[AgentAction]:
        """Parse simple action format."""
        if not isinstance(data, dict):
            raise ParseError(
                "Simple action format must be object",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
            )

        action_field = self.config.action_field
        input_field = self.config.input_field

        if action_field not in data:
            raise ParseError(
                f"Missing required '{action_field}' field",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"missing_field": action_field},
            )

        action_name = data[action_field]
        if not isinstance(action_name, str) or not action_name.strip():
            raise ParseError(
                f"'{action_field}' must be non-empty string",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
            )

        action_input = data.get(input_field, {})
        if not isinstance(action_input, dict):
            raise ParseError(
                f"'{input_field}' must be object",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
            )

        reasoning = data.get(self.config.reasoning_field, f"Using {action_name}")

        action = self._create_safe_action(
            tool=action_name, tool_input=action_input, reasoning=reasoning
        )

        return [action]

    def _parse_agent_format(self, data: Any, content: str) -> list[AgentAction] | AgentFinish:
        """Parse agent-specific format."""
        if not isinstance(data, dict):
            raise ParseError(
                "Agent format must be object", ParseErrorType.JSON_ERROR, content, recoverable=True
            )

        # Check for type field
        type_field = self.config.type_field
        if self.config.require_type_field and type_field not in data:
            raise ParseError(
                f"Missing required '{type_field}' field",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"missing_field": type_field},
            )

        response_type = data.get(type_field, "").lower()

        if response_type == "action":
            return self._parse_agent_action(data, content)
        elif response_type == "finish":
            return self._parse_agent_finish(data, content)
        elif not self.config.require_type_field:
            # Try to infer type from fields
            if self.config.action_field in data:
                return self._parse_agent_action(data, content)
            elif self.config.output_field in data:
                return self._parse_agent_finish(data, content)
            else:
                # Default to finish with the whole object as output
                return self._create_safe_finish(
                    output=json.dumps(data), reasoning="No clear type - treating as final output"
                )
        else:
            raise ParseError(
                f"Unknown response type: '{response_type}'",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"response_type": response_type, "expected": ["action", "finish"]},
            )

    def _parse_agent_action(self, data: dict[str, Any], content: str) -> list[AgentAction]:
        """Parse agent action format."""
        action_field = self.config.action_field
        if action_field not in data:
            raise ParseError(
                f"Action type missing '{action_field}' field",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"missing_field": action_field},
            )

        action_name = data[action_field]
        if not isinstance(action_name, str) or not action_name.strip():
            raise ParseError(
                f"'{action_field}' must be non-empty string",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
            )

        action_input = data.get(self.config.input_field, {})
        reasoning = data.get(self.config.reasoning_field, f"Using {action_name}")

        action = self._create_safe_action(
            tool=action_name, tool_input=action_input, reasoning=reasoning
        )

        return [action]

    def _parse_agent_finish(self, data: dict[str, Any], content: str) -> AgentFinish:
        """Parse agent finish format."""
        output_field = self.config.output_field
        if output_field not in data:
            raise ParseError(
                f"Finish type missing '{output_field}' field",
                ParseErrorType.JSON_ERROR,
                content,
                recoverable=True,
                context={"missing_field": output_field},
            )

        output = data[output_field]
        reasoning = data.get(self.config.reasoning_field, "Final answer provided")

        return self._create_safe_finish(output=str(output), reasoning=reasoning)

    def _parse_custom_format(self, data: Any, content: str) -> list[AgentAction] | AgentFinish:
        """Parse custom format using custom schema."""
        if not self.config.custom_schema:
            raise ParseError(
                "Custom format requires custom_schema configuration",
                ParseErrorType.VALIDATION_ERROR,
                content,
                recoverable=False,
            )

        # This is a simplified implementation - in practice you might use
        # a JSON schema validation library like jsonschema
        schema = self.config.custom_schema

        # Basic validation against schema
        if self.config.validate_schema:
            self._validate_against_schema(data, schema, content)

        # Extract based on schema definition
        if "action_key" in schema and schema["action_key"] in data:
            # Parse as action
            action_key = schema["action_key"]
            input_key = schema.get("input_key", "input")

            action = self._create_safe_action(
                tool=data[action_key],
                tool_input=data.get(input_key, {}),
                reasoning=data.get("reasoning", "Custom format action"),
            )
            return [action]

        elif "output_key" in schema and schema["output_key"] in data:
            # Parse as finish
            output_key = schema["output_key"]
            return self._create_safe_finish(
                output=data[output_key], reasoning=data.get("reasoning", "Custom format finish")
            )

        else:
            raise ParseError(
                "Data doesn't match custom schema",
                ParseErrorType.VALIDATION_ERROR,
                content,
                recoverable=True,
                context={"schema": schema},
            )

    def _validate_against_schema(self, data: Any, schema: dict[str, Any], content: str) -> None:
        """Basic schema validation - can be extended with proper JSON schema."""
        required_fields = schema.get("required", [])

        if not isinstance(data, dict):
            raise ParseError(
                "Custom schema expects object",
                ParseErrorType.VALIDATION_ERROR,
                content,
                recoverable=True,
            )

        for field in required_fields:
            if field not in data:
                raise ParseError(
                    f"Custom schema missing required field: {field}",
                    ParseErrorType.VALIDATION_ERROR,
                    content,
                    recoverable=True,
                    context={"missing_field": field, "required": required_fields},
                )

    def parse_error_recovery(self, error: ParseError) -> AgentAction:
        """Create recovery action for JSON parsing errors."""
        return self._create_safe_action(
            tool="_json_parse_error",
            tool_input={
                "error": str(error),
                "error_type": error.error_type.value,
                "context": error.context,
                "schema_type": self.config.schema_type.value,
                "guidance": self._get_json_guidance(),
                "examples": self._get_json_examples(),
                "raw_output": error.raw_output,
            },
            reasoning=(
                f"Reflecting on JSON parsing error for {self.config.schema_type.value} format"
            ),
            error=str(error),
        )

    def _get_json_guidance(self) -> str:
        """Get schema-specific JSON guidance."""
        if self.config.schema_type == JsonSchemaType.OPENAI_FUNCTIONS:
            return (
                "Use OpenAI function format: "
                '{"name": "tool_name", "arguments": {...}} '
                'or {"function_calls": [{"name": "tool", "arguments": {...}}]}'
            )
        elif self.config.schema_type == JsonSchemaType.SIMPLE_ACTION:
            return (
                f'Use simple action format: {{"{self.config.action_field}": "tool_name", '
                f'"{self.config.input_field}": {{}}}}'
            )
        elif self.config.schema_type == JsonSchemaType.AGENT_FORMAT:
            return (
                f"Use agent format: "
                f'{{"{self.config.type_field}": "action", '
                f'"{self.config.action_field}": "tool", "{self.config.input_field}": {{}}}} '
                f'or {{"{self.config.type_field}": "finish", '
                f'"{self.config.output_field}": "answer"}}'
            )
        else:
            return "Ensure JSON is valid and matches the expected schema"

    def _get_json_examples(self) -> dict[str, str]:
        """Get schema-specific examples."""
        if self.config.schema_type == JsonSchemaType.OPENAI_FUNCTIONS:
            return {
                "single_function": '{"name": "calculator", "arguments": {"expression": "5 + 3"}}',
                "multiple_functions": (
                    '{"function_calls": [{"name": "search", "arguments": {"query": "weather"}}]}'
                ),
            }
        elif self.config.schema_type == JsonSchemaType.AGENT_FORMAT:
            return {
                "action": (
                    f'{{"{self.config.type_field}": "action", '
                    f'"{self.config.action_field}": "calculator", '
                    f'"{self.config.input_field}": {{"expression": "5 + 3"}}}}'
                ),
                "finish": (
                    f'{{"{self.config.type_field}": "finish", '
                    f'"{self.config.output_field}": "The answer is 8"}}'
                ),
            }
        else:
            return {
                "action": (
                    f'{{"{self.config.action_field}": "calculator", '
                    f'"{self.config.input_field}": {{"expression": "5 + 3"}}}}'
                ),
                "general": '{"key": "value", "nested": {"data": "here"}}',
            }
