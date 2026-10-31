"""Auth behavior uses storage/strategy ports and never requires an infrastructure client."""

import asyncio
import threading
from datetime import UTC, datetime, timedelta
from unittest.mock import create_autospec

import pytest
from mas.core.auth.credentials.models import RecoveryResult, StoredCredential, TokenSet
from mas.core.auth.credentials.ports import CredentialStore, ServerConfigStore
from mas.core.auth.ports import AuthStrategy
from mas.core.auth.service import AuthService, AuthStrategyRegistry


@pytest.fixture
def auth_case():
    loop_thread = threading.get_ident()
    stored = StoredCredential(
        user_id="member",
        server_identifier="issuer",
        access_token="expired",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )
    store = create_autospec(CredentialStore, instance=True)
    configs = create_autospec(ServerConfigStore, instance=True)
    strategy = create_autospec(AuthStrategy, instance=True)
    strategy.scheme_type = "oauth2"

    def find(user_id, server_identifier, scheme_type=""):
        assert threading.get_ident() != loop_thread, "Credential I/O blocked the event loop"
        return stored.model_copy(deep=True)

    def config(user_id, server_identifier):
        assert threading.get_ident() != loop_thread, "Config I/O blocked the event loop"
        return None

    def save(credential):
        nonlocal stored
        assert threading.get_ident() != loop_thread, "Credential writes blocked the event loop"
        stored = credential.model_copy(deep=True)

    store.find_by_server.side_effect = find
    store.upsert.side_effect = save
    configs.find_by_server.side_effect = config
    strategy.attempt_recovery.return_value = RecoveryResult(
        recovered=True,
        should_retry=True,
        reason="Refreshed",
        new_token_set=TokenSet(
            access_token="fresh",
            expires_at=datetime.now(UTC) + timedelta(hours=1),
        ),
    )
    strategy.build_headers.side_effect = lambda credential: {
        "Authorization": "Bearer " + credential.access_token
    }
    registry = AuthStrategyRegistry()
    registry.register(strategy)
    return AuthService(store, registry, configs), store, strategy


async def test_refresh_persists_before_presenting_headers_without_blocking_loop(auth_case):
    auth, store, strategy = auth_case
    headers = await auth.get_headers("member", "issuer")
    assert headers == {"Authorization": "Bearer fresh"}
    store.upsert.assert_called_once()
    strategy.attempt_recovery.assert_awaited_once()
    assert await auth.get_valid_token("member", "issuer") == "fresh"
    strategy.attempt_recovery.assert_awaited_once()


async def test_unexpected_refresh_failure_propagates_without_rewriting_credentials(auth_case):
    auth, store, strategy = auth_case
    strategy.attempt_recovery.side_effect = OSError("Token service is unavailable")
    with pytest.raises(OSError, match="Token service is unavailable"):
        await auth.get_headers("member", "issuer")
    store.upsert.assert_not_called()


async def test_async_binding_keeps_store_reads_off_loop_and_returns_the_existing_handle(auth_case):
    auth, _, _ = auth_case
    credential = await auth.bind_async("member", "issuer", "oauth2")
    assert credential is not None
    assert await credential.get_headers() == {"Authorization": "Bearer fresh"}


@pytest.mark.parametrize("operation", ["headers", "bind"])
async def test_cancellation_drains_credential_read_before_returning(auth_case, operation):
    auth, store, _ = auth_case
    entered, released, finished = threading.Event(), threading.Event(), threading.Event()

    def blocked_read(*args):
        entered.set()
        assert released.wait(5), "Test did not release credential read"
        finished.set()
        return None

    store.find_by_server.side_effect = blocked_read
    task = asyncio.create_task(
        auth.get_headers("member", "issuer")
        if operation == "headers"
        else auth.bind_async("member", "issuer")
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        released.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert finished.is_set()
