"""Validation components for tool execution."""

import logging
from typing import Any

from jsonschema import ValidationError as JsonSchemaValidationError
from jsonschema import validate as validate_json

from mas.application.ports.tool import BaseTool
from mas.application.tools.interfaces import ExecutionValidator

logger = logging.getLogger(__name__)


class ArgumentValidator(ExecutionValidator):
    """Validates tool arguments against schema using global_utils validation."""

    def __init__(self, strict: bool = True):
        self.strict = strict
        self.name = "ArgumentValidator"

    async def validate(
        self, tool: BaseTool, args: dict[str, Any], context: dict[str, Any] | None = None
    ) -> tuple[bool, str | None]:
        """Validate arguments against tool schema."""
        try:
            if getattr(tool, "args_schema", None):
                validate_json(instance=args, schema=tool.get_args_schema_json())
            elif self.strict:
                return False, f"Tool {tool.name} has no argument schema"

            return True, None

        except JsonSchemaValidationError as error:
            return False, f"Validation error: {error.message}"
        except Exception as e:
            logger.error("tool.validation_error", extra={"tool_name": tool.name, "error": str(e)})
            return False, f"Validation error: {e}"


class CompositeValidator(ExecutionValidator):
    """Combines multiple validators."""

    def __init__(self, validators: list[ExecutionValidator], fail_fast: bool = True):
        self.validators = validators
        self.fail_fast = fail_fast
        self.name = "CompositeValidator"

    async def validate(
        self, tool: BaseTool, args: dict[str, Any], context: dict[str, Any] | None = None
    ) -> tuple[bool, str | None]:
        """Run all validators."""
        errors = []

        for validator in self.validators:
            try:
                is_valid, error_msg = await validator.validate(tool, args, context)
                if not is_valid:
                    if self.fail_fast:
                        return False, error_msg
                    else:
                        errors.append(f"{getattr(validator, 'name', 'Unknown')}: {error_msg}")
            except Exception as e:
                error_msg = f"Validator {getattr(validator, 'name', 'Unknown')} failed: {e}"
                if self.fail_fast:
                    return False, error_msg
                else:
                    errors.append(error_msg)

        if errors:
            return False, "; ".join(errors)

        return True, None
