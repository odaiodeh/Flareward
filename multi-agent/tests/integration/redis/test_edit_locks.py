"""Actual Redis proves atomic claims, occurrence fencing, expiry and safe corrupt-state handling."""

import asyncio
import os
from uuid import uuid4

import pytest
from mas.application.collaboration.editing import (
    EditEntityKind,
    EditLease,
    EditLockScope,
    EditLockUnavailable,
)
from outbound.redis.edit_locks import RedisEditLockStore, edit_lock_key
from outbound.redis_client import owned_redis


@pytest.fixture
async def editing():
    uri = os.environ.get("UNIFAI_TEST_REDIS_URI")
    if not uri:
        pytest.skip("Set UNIFAI_TEST_REDIS_URI for atomic editing lease contracts")
    scope = EditLockScope(
        team_id="lease-test-" + uuid4().hex, kind=EditEntityKind.RESOURCE, entity_id="resource"
    )
    async with owned_redis(uri, decode_responses=True) as redis:
        try:
            yield RedisEditLockStore(redis), redis, scope
        finally:
            keys = [
                key
                async for key in redis.scan_iter(
                    match=f"mas:collab:editlock:team:{scope.team_id}:*"
                )
            ]
            if keys:
                await redis.delete(*keys)


async def test_concurrent_editors_have_one_winner_and_cannot_release_or_renew_each_other(editing):
    store, _, scope = editing
    leases = [
        EditLease(user_id="human", display_name="Human", lease_id=str(index)) for index in range(12)
    ]
    results = await asyncio.gather(*(store.acquire(scope, lease, 30) for lease in leases))
    winners = [lease for lease, conflict in zip(leases, results, strict=True) if conflict is None]
    assert len(winners) == 1
    winner = winners[0]
    loser = next(lease for lease in leases if lease != winner)
    assert not await store.renew(scope, loser, 30)
    await store.release(scope, loser)
    assert await store.holders((scope,)) == (winner,)
    assert await store.renew(scope, winner, 30)
    await store.release(scope, winner)
    assert await store.holders((scope,)) == (None,)


async def test_expired_heartbeat_cannot_reacquire_or_disturb_a_later_editor(editing):
    store, redis, scope = editing
    old = EditLease(user_id="human", display_name="Human", lease_id="old-editor")
    current = old.model_copy(update={"lease_id": "new-editor"})
    assert await store.acquire(scope, old, 30) is None
    await redis.pexpire(edit_lock_key(scope), 1)
    async with asyncio.timeout(2):
        while await redis.exists(edit_lock_key(scope)):
            await asyncio.sleep(0.01)
    assert not await store.renew(scope, old, 30)
    assert not await redis.exists(edit_lock_key(scope))
    assert await store.acquire(scope, current, 30) is None
    await store.release(scope, old)
    assert not await store.renew(scope, old, 30)
    assert await store.holders((scope,)) == (current,)


async def test_actor_and_entity_kind_are_separate_lease_boundaries(editing):
    store, _, scope = editing
    owner = EditLease(user_id="alice", display_name="Alice", lease_id="occurrence")
    other = owner.model_copy(update={"user_id": "bob"})
    assert await store.acquire(scope, owner, 30) is None
    assert await store.acquire(scope, other, 30) == owner
    await store.release(scope, other)
    assert await store.holders((scope,)) == (owner,)
    blueprint = scope.model_copy(update={"kind": EditEntityKind.BLUEPRINT})
    assert await store.acquire(blueprint, other, 30) is None
    assert await store.holders((scope, blueprint)) == (owner, other)


@pytest.mark.parametrize("payload", ["invalid-json", "[]", '{"user_id":"someone"}'])
@pytest.mark.parametrize("operation", ["acquire", "renew", "release", "holders"])
async def test_unreadable_state_is_not_silently_claimed_or_deleted(editing, payload, operation):
    store, redis, scope = editing
    await redis.set(edit_lock_key(scope), payload, ex=30)
    with pytest.raises(EditLockUnavailable):
        if operation == "holders":
            await store.holders((scope,))
        elif operation == "release":
            await store.release(scope, EditLease(user_id="human", display_name="Human"))
        else:
            await getattr(store, operation)(
                scope, EditLease(user_id="human", display_name="Human"), 30
            )
    assert await redis.get(edit_lock_key(scope)) == payload


async def test_legacy_holder_payload_is_readable_without_exposing_a_new_editor_to_stale_release(
    editing,
):
    store, redis, scope = editing
    await redis.set(edit_lock_key(scope), '{"user_id":"human","display_name":"Human"}', ex=30)
    modern = EditLease(user_id="human", display_name="Human", lease_id="new-editor")
    assert (await store.acquire(scope, modern, 30)).lease_id is None
    await store.release(scope, modern)
    assert (await store.holders((scope,)))[0].lease_id is None
