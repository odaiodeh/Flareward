"""Real provider SDK handshakes own their HTTP clients, including failed entry."""

import asyncio
from contextlib import AsyncExitStack
from unittest.mock import Mock

import httpx
import pytest
from a2a.types import AgentCapabilities, AgentCard
from mas.application.elements.validation import ValidationCode, ValidationContext
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.nodes.a2a_agent.validator import A2AAgentNodeValidator
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.validator import McpProviderValidator
from mcp.server.fastmcp import FastMCP
from starlette.applications import Starlette
from starlette.responses import JSONResponse, Response
from starlette.routing import Route


@pytest.mark.parametrize("provider", ["mcp", "a2a"])
@pytest.mark.parametrize("outcome", ["success", "rejected", "timeout", "cancel"])
async def test_sdk_probe_closes_http_client_without_entering_an_async_bridge(
    monkeypatch, provider, outcome
):
    clients: list[httpx.AsyncClient] = []
    client_type = httpx.AsyncClient
    entered = asyncio.Event()
    requests: list[str] = []
    bridge = Mock(side_effect=AssertionError("Native probe entered the async bridge"))
    context = ValidationContext(timeout_seconds=0.2 if outcome == "timeout" else 2)

    if provider == "mcp":
        server = FastMCP("Probe", stateless_http=True, json_response=True, log_level="ERROR")
        application = server.streamable_http_app()
        client_target = (
            "mas.elements.providers.mcp_server_client.transport."
            "streamable_http_transport.create_mcp_http_client"
        )
        bridge_target = "mas.elements.providers.mcp_server_client.validator.get_async_bridge"
        validator, config = (
            McpProviderValidator(),
            McpProviderConfig(mcp_url="http://127.0.0.1:8000/mcp", bearer_token="wire-private"),
        )
    else:
        card = AgentCard(
            name="Probe",
            description="Protocol fixture",
            url="http://127.0.0.1:8000",
            version="1",
            capabilities=AgentCapabilities(),
            default_input_modes=["text/plain"],
            default_output_modes=["text/plain"],
            skills=[],
        )

        async def agent_card(request):
            return JSONResponse(card.model_dump(mode="json", by_alias=True))

        application = Starlette(routes=[Route("/.well-known/agent-card.json", agent_card)])
        client_target = "mas.elements.providers.a2a_client.client.httpx.AsyncClient"
        bridge_target = "mas.elements.nodes.a2a_agent.validator.get_async_bridge"
        validator, config = (
            A2AAgentNodeValidator(),
            A2AAgentNodeConfig(
                base_url="http://127.0.0.1:8000",
                auth_method="access_token",
                bearer_token="wire-private",
            ),
        )

    async def endpoint(scope, receive, send):
        if scope["type"] == "http":
            assert dict(scope["headers"])[b"authorization"] == b"Bearer wire-private"
            requests.append(scope["method"])
            if scope["method"] in {"GET", "POST"}:
                entered.set()
                if outcome == "rejected":
                    await Response(status_code=401)(scope, receive, send)
                    return
                if outcome in {"timeout", "cancel"}:
                    await asyncio.Future()
        await application(scope, receive, send)

    def client(**kwargs):
        instance = client_type(transport=httpx.ASGITransport(app=endpoint), **kwargs)
        clients.append(instance)
        return instance

    monkeypatch.setattr(client_target, client)
    monkeypatch.setattr(bridge_target, bridge)
    async with AsyncExitStack() as resources:
        if provider == "mcp":
            await resources.enter_async_context(application.router.lifespan_context(application))
        task = asyncio.create_task(validator.validate_async(config, context))
        async with asyncio.timeout(3):
            await entered.wait()
            if outcome == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                report = await task
                if outcome == "success":
                    assert report.is_valid, report
                    if provider == "mcp":
                        # Initialize, initialized notification, and tools/list cross the SDK wire.
                        assert requests.count("POST") >= 3
                else:
                    code = (
                        ValidationCode.INVALID_CREDENTIALS
                        if outcome == "rejected"
                        else ValidationCode.NETWORK_TIMEOUT
                    )
                    assert not report.is_valid and report.messages[0].code == code, report
                    assert "wire-private" not in report.model_dump_json()
    assert clients and all(instance.is_closed for instance in clients)
    bridge.assert_not_called()
