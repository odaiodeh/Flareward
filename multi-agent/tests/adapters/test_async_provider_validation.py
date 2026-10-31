"""Native provider probes await their transports, preserve identity, and never enter a bridge."""

import asyncio
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import Mock, create_autospec

import pytest
from mas.application.elements.validation import ValidationCode, ValidationContext
from mas.core.auth.credentials.credential import AuthCredential
from mas.core.auth.errors import TokenExpiredError
from mas.core.auth.service import AuthService
from mas.elements.nodes.a2a_agent.config import A2AAgentNodeConfig
from mas.elements.nodes.a2a_agent.validator import A2AAgentNodeValidator
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.validator import McpProviderValidator


@pytest.fixture
def native_context(monkeypatch):
    bridge = Mock(side_effect=AssertionError("Native validation entered the async bridge"))
    monkeypatch.setattr(
        "mas.elements.providers.mcp_server_client.validator.get_async_bridge", bridge
    )
    monkeypatch.setattr("mas.elements.nodes.a2a_agent.validator.get_async_bridge", bridge)
    auth = create_autospec(AuthService, instance=True)
    credential = create_autospec(AuthCredential, instance=True)
    credential.get_headers.return_value = {"Authorization": "Bearer stored-private"}
    auth.bind_async.return_value = credential
    context = ValidationContext(user_id="workspace", credential_user_id="human", auth_service=auth)
    return context, auth, credential, bridge


async def test_mcp_probe_awaits_factory_and_binds_the_human_for_sign_in(native_context):
    context, auth, credential, bridge = native_context
    factory = create_autospec(McpProviderFactory, instance=True)
    loop = asyncio.get_running_loop()

    async def create(config, **kwargs):
        assert asyncio.get_running_loop() is loop
        assert kwargs["auth_credential"] is credential

    factory.create_async.side_effect = create
    config = McpProviderConfig(
        mcp_url="https://mcp.invalid",
        auth_method="sign_in",
        server_identifier="inspection",
        scheme_type="api_key",
    )
    report = await McpProviderValidator(factory).validate_async(config, context)
    assert report.is_valid
    auth.bind_async.assert_awaited_once_with("human", "inspection", scheme_type="api_key")
    auth.bind.assert_not_called()
    bridge.assert_not_called()


async def test_mcp_sign_in_does_not_probe_anonymously_when_no_credential_exists(native_context):
    context, auth, _, bridge = native_context
    auth.bind_async.return_value = auth.discover.return_value = None
    factory = create_autospec(McpProviderFactory, instance=True)
    report = await McpProviderValidator(factory).validate_async(
        McpProviderConfig(mcp_url="https://mcp.invalid", auth_method="sign_in"), context
    )
    assert not report.is_valid and report.messages[0].code == ValidationCode.INVALID_CREDENTIALS
    factory.create_async.assert_not_awaited()
    bridge.assert_not_called()


@pytest.mark.parametrize("expired", [False, True])
async def test_mcp_bound_credentials_cannot_fall_back_to_an_anonymous_probe(
    native_context, monkeypatch, expired
):
    context, _, credential, bridge = native_context
    if expired:
        credential.get_headers.side_effect = TokenExpiredError("private-auth-detail")
    else:
        credential.get_headers.return_value = {}
    transport = Mock(side_effect=AssertionError("Unauthenticated transport was opened"))
    monkeypatch.setattr(
        "mas.elements.providers.mcp_server_client.mcp_provider.McpServerClient", transport
    )
    report = await McpProviderValidator().validate_async(
        McpProviderConfig(mcp_url="https://mcp.invalid", auth_method="sign_in"), context
    )
    assert not report.is_valid and report.messages[0].code == ValidationCode.INVALID_CREDENTIALS
    assert "private-auth-detail" not in report.model_dump_json()
    transport.assert_not_called()
    bridge.assert_not_called()


@pytest.mark.parametrize(
    "failure,code",
    [
        (RuntimeError("private-provider-detail"), ValidationCode.ENDPOINT_UNREACHABLE),
        (ValueError("403 private-provider-detail"), ValidationCode.INVALID_CREDENTIALS),
    ],
)
async def test_mcp_failures_preserve_codes_without_exporting_provider_details(
    native_context, failure, code
):
    context, _, _, _ = native_context
    factory = create_autospec(McpProviderFactory, instance=True)
    factory.create_async.side_effect = failure
    report = await McpProviderValidator(factory).validate_async(
        McpProviderConfig(mcp_url="https://mcp.invalid"), context
    )
    assert not report.is_valid and report.messages[0].code == code
    assert "private-provider-detail" not in report.model_dump_json()


async def test_a2a_probe_awaits_client_and_preserves_the_human_credential(
    native_context, monkeypatch
):
    context, auth, _, bridge = native_context
    loop = asyncio.get_running_loop()
    closed = asyncio.Event()

    @asynccontextmanager
    async def client(**kwargs):
        assert asyncio.get_running_loop() is loop
        assert kwargs["headers"] == {"Authorization": "Bearer stored-private"}
        try:
            yield SimpleNamespace(agent_card={"name": "Agent"})
        finally:
            closed.set()

    monkeypatch.setattr("mas.elements.nodes.a2a_agent.validator.A2AClient", client)
    report = await A2AAgentNodeValidator().validate_async(
        A2AAgentNodeConfig(
            base_url="https://agent.invalid", auth_method="inspection", scheme_type="api_key"
        ),
        context,
    )
    assert report.is_valid and closed.is_set()
    auth.bind_async.assert_awaited_once_with("human", "inspection", scheme_type="api_key")
    auth.bind.assert_not_called()
    bridge.assert_not_called()


@pytest.mark.parametrize("provider", ["mcp", "a2a"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_probe_timeout_waits_for_async_transport_cleanup(
    native_context, monkeypatch, provider, cancel
):
    context, _, _, _ = native_context
    entered, cleanup, release, closed = (asyncio.Event() for _ in range(4))

    @asynccontextmanager
    async def transport(**kwargs):
        entered.set()
        try:
            await asyncio.Future()
            yield SimpleNamespace(agent_card={})
        finally:
            cleanup.set()
            await release.wait()
            closed.set()

    context = context.model_copy(update={"timeout_seconds": 0.02})
    if provider == "mcp":
        factory = create_autospec(McpProviderFactory, instance=True)

        async def create(*args, **kwargs):
            async with transport():
                pass

        factory.create_async.side_effect = create
        operation = McpProviderValidator(factory).validate_async(
            McpProviderConfig(mcp_url="https://mcp.invalid"), context
        )
    else:
        monkeypatch.setattr("mas.elements.nodes.a2a_agent.validator.A2AClient", transport)
        operation = A2AAgentNodeValidator().validate_async(
            A2AAgentNodeConfig(base_url="https://agent.invalid"), context
        )
    task = asyncio.create_task(operation)
    try:
        async with asyncio.timeout(2):
            await entered.wait()
            if cancel:
                task.cancel()
            await cleanup.wait()
        if cancel:
            # Let the deadline fire while SDK cleanup is still in progress.
            await asyncio.sleep(0.03)
            task.cancel()
            await asyncio.sleep(0)
        assert not task.done() and not closed.is_set()
    finally:
        release.set()
    if cancel:
        with pytest.raises(asyncio.CancelledError):
            await task
    else:
        report = await task
        assert not report.is_valid and report.messages[0].code == ValidationCode.NETWORK_TIMEOUT
    assert closed.is_set()
