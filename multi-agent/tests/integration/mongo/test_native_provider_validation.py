"""Real native API/storage/credential paths use installed provider validators without a bridge."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.core.identity import Identity
from mas.elements.nodes.a2a_agent.spec.spec import A2AAgentNodeElementSpec
from mas.elements.providers.mcp_server_client.spec.spec import McpProviderElementSpec
from support.blueprint_http import library_api


async def test_native_resource_and_blueprint_probes_await_mcp_a2a_and_real_human_credentials(
    inspection_settings, mongo_database, monkeypatch
):
    loop = asyncio.get_running_loop()
    bridge = Mock(side_effect=AssertionError("Native API entered the legacy async bridge"))
    monkeypatch.setattr(
        "mas.elements.providers.mcp_server_client.validator.get_async_bridge", bridge
    )
    monkeypatch.setattr("mas.elements.nodes.a2a_agent.validator.get_async_bridge", bridge)
    probes = []

    async def create_mcp(self, config, *, auth_credential):
        assert asyncio.get_running_loop() is loop
        assert await auth_credential.get_headers() == {
            "Authorization": "Bearer probe-server-private"
        }
        probes.append("mcp")

    @asynccontextmanager
    async def a2a_client(**kwargs):
        assert asyncio.get_running_loop() is loop
        assert kwargs["headers"] == {"Authorization": "Bearer probe-server-private"}
        probes.append("a2a")
        yield SimpleNamespace(agent_card={"name": "Agent"})

    monkeypatch.setattr(
        "mas.elements.providers.mcp_server_client.mcp_provider_factory.McpProviderFactory.create_async",
        create_mcp,
    )
    monkeypatch.setattr("mas.elements.nodes.a2a_agent.validator.A2AClient", a2a_client)
    elements = ElementRegistry()
    elements.register_spec_class(McpProviderElementSpec)
    elements.register_spec_class(A2AAgentNodeElementSpec)
    async with library_api(
        inspection_settings, Identity.team("workspace"), elements=elements
    ) as http:
        resources = []
        for spec, config in (
            (
                McpProviderElementSpec,
                {
                    "mcp_url": "https://mcp.invalid",
                    "auth_method": "sign_in",
                    "server_identifier": "inspection",
                    "scheme_type": "api_key",
                },
            ),
            (
                A2AAgentNodeElementSpec,
                {
                    "base_url": "https://agent.invalid",
                    "auth_method": "inspection",
                    "scheme_type": "api_key",
                },
            ),
        ):
            created = await http.post(
                "/api/resources",
                json={
                    "category": spec.category.value,
                    "type": spec.type_key,
                    "name": spec.name,
                    "config": config,
                },
            )
            assert created.status_code == 201, created.text
            rid = created.json()["rid"]
            resources.append((spec, rid))
            saved = await http.post(f"/api/resources/{rid}/validation", json={})
            assert saved.status_code == 200 and saved.json()["is_valid"], saved.text
            inline = await http.post(
                "/api/resources/configuration/validation",
                json={"category": spec.category.value, "type": spec.type_key, "config": config},
            )
            assert inline.status_code == 200 and inline.json()["is_valid"], inline.text
        draft = {
            "plan": [],
            **{spec.category.value: [{"rid": "$ref:" + rid}] for spec, rid in resources},
        }
        inspected = await http.post("/api/blueprints/draft/validation", json={"spec": draft})
        assert inspected.status_code == 200 and inspected.json()["is_valid"], inspected.text
        created = await http.post("/api/blueprints", json={"spec": draft})
        assert created.status_code == 201, created.text
        saved = await http.post(
            f"/api/blueprints/{created.json()['blueprint_id']}/validation", json={}
        )
        assert saved.status_code == 200 and saved.json()["is_valid"], saved.text
        assert "probe-server-private" not in saved.text + inspected.text
    assert probes.count("mcp") == probes.count("a2a") == 4
    bridge.assert_not_called()
    stored = await mongo_database.credentials.find_one({"user_id": "human"})
    assert stored["access_token"].startswith("gAAAAA")
