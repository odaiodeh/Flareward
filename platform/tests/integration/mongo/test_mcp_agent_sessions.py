"""Saved provider/tool references drive actual agents across receiver processes."""

import hashlib
from uuid import uuid4

import pytest
from pydantic import BaseModel
from support.agent_session import ELEMENT_SPECIFICATIONS
from support.agent_session_assertions import assert_agent_results
from support.agent_session_http import create_mcp_agent_session, execute_agent_turn
from support.blueprint_http import library_api
from support.server import api_process

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.services.identity.domain import Identity
from plugins.mcp.elements.mcp_proxy.spec.spec import McpProxyToolElementSpec
from plugins.mcp.elements.mcp_server_client.spec.spec import McpProviderElementSpec


class McpSettings(BaseModel):
    test_mcp_evidence: str


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_saved_mcp_dependency_schema_and_execution_survive_resource_edits(
    secret_settings,
    tmp_path,
    profile,
):
    evidence = hashlib.sha256(uuid4().bytes).hexdigest()
    elements = ElementRegistry()
    for specification in (*ELEMENT_SPECIFICATIONS, McpProviderElementSpec, McpProxyToolElementSpec):
        elements.register_spec_class(specification)
    settings = secret_settings.model_copy(update={"library": True})
    async with api_process(
        McpSettings(test_mcp_evidence=evidence),
        tmp_path / "mcp.log",
        factory="support.mcp_service:create_app",
        health_path="/health",
    ) as service:
        endpoint = str(service.base_url).rstrip("/") + "/mcp"
        async with library_api(settings, Identity.user("owner"), elements=elements) as http:
            session_id, definition = await create_mcp_agent_session(http, endpoint, profile=profile)
            for turn in (1, 2):
                _, session = await execute_agent_turn(
                    http,
                    session_id,
                    uuid4().hex,
                    f"Read remote evidence, turn {turn}",
                )
                assert all(
                    evidence in result.content for result in assert_agent_results(session, turn)
                )
                assert evidence in session.graph_state.output
                health = await service.get("/health")
                assert health.json()["calls"] == ["read_remote_evidence"] * (2 * turn)
                if turn == 1:
                    provider = next(
                        item
                        for item in definition["implementation"]["resources"]
                        if item["key"]["category"] == "providers"
                    )
                    edited = await http.put(
                        "/api/resources/" + provider["key"]["rid"],
                        json={
                            "config": {"mcp_url": "http://127.0.0.1:1/mcp"},
                            "expected_version": 1,
                        },
                    )
                    assert edited.status_code == 200, edited.text
