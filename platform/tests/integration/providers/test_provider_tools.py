"""The installed provider/tool factories resolve real MCP metadata before consumption."""

import json

import httpx
import pytest
from support.mcp_service import create_app
from support.scenarios import resource

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.builder import ElementBundleBuilder
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.elements.exceptions import PluginConfigurationError
from flareward.resources.domain.categories import ResourceCategory
from plugins.mcp.elements.mcp_proxy.mcp_proxy_tool import McpProxyToolError
from plugins.mcp.elements.mcp_proxy.spec.spec import McpProxyToolElementSpec
from plugins.mcp.elements.mcp_server_client.spec.spec import McpProviderElementSpec


@pytest.fixture
def provider_elements():
    registry = ElementRegistry()
    for specification in (McpProviderElementSpec, McpProxyToolElementSpec):
        registry.register_spec_class(specification)
    return registry


@pytest.fixture
def mcp_transport(monkeypatch):
    app = create_app()
    clients = []
    client_type = httpx.AsyncClient

    def client(**kwargs):
        instance = client_type(transport=httpx.ASGITransport(app), **kwargs)
        clients.append(instance)
        return instance

    monkeypatch.setattr(
        "plugins.mcp.elements.mcp_server_client.transport."
        "streamable_http_transport.create_mcp_http_client",
        client,
    )
    yield app, clients
    assert clients and all(client.is_closed for client in clients)


@pytest.mark.parametrize("name", ["read_remote_evidence", "missing", "read_failure"])
async def test_selected_provider_tool_has_real_schema_and_preserves_failure_semantics(
    provider_elements,
    mcp_transport,
    name,
):
    app, _ = mcp_transport
    async with app.router.lifespan_context(app):
        tool = resource(
            "selected",
            type_key="mcp_proxy",
            config={"provider": "$ref:remote", "tool_name": name},
        )
        provider = resource(
            "remote",
            category=ResourceCategory.PROVIDER,
            type_key="mcp_server",
            config={"mcp_url": "http://127.0.0.1:8000/mcp"},
        )
        bundle = ElementBundleResolver(provider_elements).resolve(tool.key, [tool, provider])
        if name == "missing":
            with pytest.raises(PluginConfigurationError, match="exactly one tool"):
                async with ElementBundleBuilder(provider_elements).build(bundle):
                    pytest.fail("Unavailable tool must fail construction")
            return
        async with ElementBundleBuilder(provider_elements).build(bundle) as built:
            definition = built.element.to_definition()
            assert definition.name == name and definition.description
            assert definition.parameters["type"] == "object"
            if name == "read_failure":
                with pytest.raises(McpProxyToolError, match="execution failed") as failure:
                    await built.element.run()
                assert "remote-private-detail" not in str(failure.value)
            else:
                assert json.loads(await built.element.run()) == {
                    "evidence": "wire-evidence",
                    "source": "mcp-protocol",
                }
