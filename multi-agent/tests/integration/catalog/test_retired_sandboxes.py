"""Retired tool sandboxes fail clearly while engine execution profiles remain usable."""

import pytest
from mas.application.elements.catalog.service import CatalogService
from mas.blueprints.models.blueprint import BlueprintDraft
from mas.blueprints.schema import blueprint_schemas
from mas.core.enums import ResourceCategory
from mas.domain.execution.context import ExecutionContext
from mas.elements.nodes.claude_agent.config import ClaudeAgentNodeConfig
from mas.elements.nodes.deep_agent.config import DeepAgentNodeConfig
from outbound.run_engine.compiler import ProgramCompiler
from pydantic import ValidationError
from runengine.coordination.models import RunRequest
from runengine.invocation.config import OpenShellRunnerConfig
from runengine.programs.graph.inputs import GraphProgramInput
from support.elements import DependencySpec
from support.scenarios import echo_graph, publish

from bootstrap.elements import installed_elements


@pytest.mark.parametrize(
    "schema,data",
    [
        (DeepAgentNodeConfig, {"llm": "$ref:model"}),
        (ClaudeAgentNodeConfig, {"vertex_project_id": "project"}),
    ],
)
def test_agent_rejects_sandbox_but_reads_old_unused_default(schema, data):
    with pytest.raises(ValidationError, match="retired"):
        schema.model_validate({**data, "sandbox": "$ref:old-sandbox"})
    current = schema.model_validate({**data, "sandbox": None})
    assert "sandbox" not in current.model_dump()
    assert "sandbox" not in schema.model_json_schema()["properties"]


def test_installed_catalog_does_not_offer_or_reinstall_sandbox_elements():
    registry = installed_elements()
    assert ResourceCategory.SANDBOX not in registry.list_categories()
    assert "sandboxes" not in CatalogService(registry).get_all_elements_summary().elements

    class RetiredSpec(DependencySpec):
        category = ResourceCategory.SANDBOX
        type_key = "openshell"

    with pytest.raises(ValueError, match="retired"):
        registry.register_spec_class(RetiredSpec)


@pytest.mark.parametrize(
    "resource",
    [
        {"rid": "$ref:saved-sandbox"},
        {
            "rid": "sandbox",
            "name": "Old",
            "type": "openshell_sandbox",
            "config": {"tls_key": "private-fixture"},
        },
    ],
)
def test_blueprints_do_not_discard_retired_sandbox_resources(application, resource):
    data = {"plan": [], "sandboxes": [resource]}
    schema = blueprint_schemas(application.elements).draft
    for parse in (schema.model_validate, BlueprintDraft.from_stored_dict):
        with pytest.raises(ValidationError) as failure:
            parse(data)
        assert any(error["loc"][0] == "sandboxes" for error in failure.value.errors())
        assert "private-fixture" not in str(failure.value)


async def test_openshell_profile_keeps_network_policy(platform, application):
    target = OpenShellRunnerConfig(
        endpoint="https://gateway.invalid",
        image="receiver:test",
        policy={
            "network_policies": {
                "api": {
                    "endpoints": [{"host": "api.example.com", "port": 443}],
                    "binaries": [{"path": "/sandbox/.venv/bin/python"}],
                }
            }
        },
    )
    compiler = ProgramCompiler(
        platform.programs,
        application.elements,
        application.applications,
        {"isolated": target},
        "isolated",
    )
    expected = target.model_dump(mode="json")
    target.policy.network_policies["api"].endpoints[0].host = "changed.example.com"
    revision = await publish(platform, "environment-profile", echo_graph("isolated"))
    request = await compiler.compile(
        revision,
        platform.owner,
        ExecutionContext(identity=platform.owner),
    )
    graph_request = RunRequest.model_validate(request.input["graph_request"])
    graph = GraphProgramInput.model_validate(graph_request.input)
    assert graph.targets["echo"] == expected
    assert not application.elements.has_spec(ResourceCategory.SANDBOX, "openshell_sandbox")
