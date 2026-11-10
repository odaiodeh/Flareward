"""Registered schemas govern blueprint types, typed dependencies, and portable validation."""

from unittest.mock import create_autospec

import pytest
from jsonschema import Draft202012Validator
from pydantic import ValidationError
from support.blueprints import dependency_blueprint
from support.elements import DependencyConfig, EchoConfig

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.templates.resolver import BlueprintResolver
from lumora.programs.templates.schema import blueprint_schemas
from lumora.resources.domain.references import ToolRef
from lumora.resources.ports import ResourceReader


def test_registry_blueprint_schema_preserves_plugin_configuration_and_exposes_it_to_clients(
    application,
):
    schemas = blueprint_schemas(application.elements)
    data = dependency_blueprint("process")
    draft = schemas.draft.model_validate(data)
    assert isinstance(draft.nodes[0].config, EchoConfig)
    assert isinstance(draft.tools[1].config, DependencyConfig)
    assert isinstance(draft.tools[1].config.dependency, ToolRef)
    assert draft.nodes[0].config.dependency.ref == "middle"
    assert draft.nodes[0].execution.profile == "process"
    Draft202012Validator.check_schema(schemas.draft.model_json_schema())
    Draft202012Validator(schemas.draft.model_json_schema()).validate(data)
    assert schemas.draft.model_validate_json(draft.model_dump_json()) == draft


@pytest.mark.parametrize(
    "node",
    [
        {"rid": "echo", "type": "unknown", "name": "Echo", "config": {}},
        {"rid": "echo", "type": "platform_dependency", "name": "Echo", "config": {}},
        {"rid": "echo", "type": "platform_echo", "name": "Echo", "config": {"dependency": 7}},
        {"rid": "echo", "type": "platform_echo", "name": "Echo"},
        {
            "rid": "$ref:echo",
            "type": "platform_echo",
            "name": "Echo",
            "config": {"dependency": "middle"},
        },
        {"rid": "", "type": "platform_echo", "name": "Echo", "config": {"dependency": "middle"}},
    ],
)
def test_registry_blueprint_schema_rejects_unregistered_mismatched_and_ambiguous_resources(
    application, node
):
    schemas = blueprint_schemas(application.elements)
    with pytest.raises(ValidationError):
        schemas.draft.model_validate({**dependency_blueprint(), "nodes": [node]})


def test_type_dispatch_uses_resource_identity_even_when_two_types_share_a_schema(application):
    schemas = blueprint_schemas(application.elements)
    data = dependency_blueprint()
    data["nodes"][0]["type"] = "platform_async_echo"
    draft = schemas.draft.model_validate(data)
    assert draft.nodes[0].type == "platform_async_echo"
    assert isinstance(draft.nodes[0].config, EchoConfig)
    source = create_autospec(ResourceReader, instance=True)
    resolved = BlueprintResolver(source, spec_schema=schemas.resolved).resolve(draft)
    assert resolved.nodes[0].type == "platform_async_echo"
    assert resolved.nodes[0].config.dependency.ref == "middle"
    source.get_visible.assert_not_called()


def test_uninstalled_categories_cannot_silently_discard_configuration():
    schemas = blueprint_schemas(ElementRegistry())
    assert schemas.draft.model_validate({"plan": [], "tools": [{"rid": "$ref:saved"}]})
    with pytest.raises(ValidationError):
        schemas.resolved.model_validate(
            {
                "plan": [],
                "tools": [
                    {
                        "rid": "tool",
                        "type": "unknown",
                        "name": "Tool",
                        "config": {"value": "must-not-disappear"},
                    }
                ],
            }
        )
