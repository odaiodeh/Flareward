"""Tool registration carries independent JSON data rather than shared mutable schemas."""

import pytest
from pydantic import ValidationError

from lumora.elements.tools.domain.models import ToolDefinition


def test_tool_schema_owns_nested_values_and_empty_defaults_are_independent():
    source = {"type": "object", "properties": {"query": {"type": "string"}}}
    definition = ToolDefinition(name="search", parameters=source)
    source["properties"]["query"]["type"] = "integer"
    assert definition.parameters["properties"]["query"]["type"] == "string"
    first, second = ToolDefinition(name="first"), ToolDefinition(name="second")
    first.parameters["properties"]["unexpected"] = {"type": "string"}
    assert second.parameters["properties"] == {}


def test_tool_schema_rejects_nonportable_runtime_objects():
    with pytest.raises(ValidationError):
        ToolDefinition(name="invalid", parameters={"runtime": object()})
