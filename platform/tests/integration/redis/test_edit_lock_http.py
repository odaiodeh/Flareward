"""Native signed-cookie/team authorization and real Redis editing leases."""

import os

import pytest
from support.team_http import team_api


@pytest.fixture
async def editors(secret_settings):
    uri = os.environ.get("LUMORA_TEST_REDIS_URI")
    if not uri:
        pytest.skip("Set LUMORA_TEST_REDIS_URI for native editing HTTP contracts")
    settings = secret_settings.model_copy(update={"library": True, "edit_locks": True})
    async with team_api(settings, uri) as team:
        yield team.team_id, team.clients, team.redis


@pytest.mark.parametrize("kind", ["resource", "blueprint"])
async def test_authenticated_editors_are_fenced_by_actor_and_occurrence(editors, kind):
    team_id, clients, _ = editors
    alice, bob = clients["alice"], clients["bob"]
    if kind == "resource":
        created = await alice.post(
            "/api/resources/resource.save",
            json={
                "teamId": team_id,
                "category": "conditions",
                "type": "router_boolean",
                "name": "Shared condition",
                "config": {"boolean_value": True},
            },
        )
        assert created.status_code == 201, created.text
        entity_id = created.json()["rid"]
    else:
        # Canonical authoring takes the selected team in its authenticated query scope.
        created = await alice.post(
            "/api/blueprints",
            params={"teamId": team_id},
            json={"spec": {"name": "Shared draft", "plan": []}},
        )
        assert created.status_code == 201, created.text
        entity_id = created.json()["blueprint_id"]
    request = {
        "teamId": team_id,
        "entityKind": kind,
        "entityId": entity_id,
        "leaseId": "first-editor",
    }
    first = await alice.post(
        "/api/collaboration/edit_lock.acquire",
        json={**request, "userId": "bob", "displayName": "Forged admin"},
    )
    assert first.status_code == 200 and first.json()["acquired"], first.text
    status = await alice.post(
        "/api/collaboration/edit_lock.statuses",
        json={
            "teamId": team_id,
            "entityKind": kind,
            "entityIds": [entity_id],
        },
    )
    assert status.json() == {"locks": {entity_id: {"userId": "alice", "displayName": "alice"}}}
    single = await alice.get(
        "/api/collaboration/edit_lock.status",
        params={"teamId": team_id, "entityKind": kind, "entityId": entity_id},
    )
    assert single.status_code == 200
    assert single.json() == {
        "locked": True,
        "lockedBy": {"userId": "alice", "displayName": "alice"},
    }
    for client, lease_id in ((bob, "first-editor"), (alice, "new-editor")):
        contender = {**request, "leaseId": lease_id}
        conflict = await client.post("/api/collaboration/edit_lock.acquire", json=contender)
        assert conflict.status_code == 200 and not conflict.json()["acquired"]
        assert conflict.json()["lockedBy"]["userId"] == "alice"
        assert (
            await client.post("/api/collaboration/edit_lock.heartbeat", json=contender)
        ).json() == {"renewed": False}
        assert (
            await client.post("/api/collaboration/edit_lock.release", json=contender)
        ).status_code == 200
    assert (await alice.post("/api/collaboration/edit_lock.heartbeat", json=request)).json() == {
        "renewed": True
    }
    assert (
        await clients["mallory"].post("/api/collaboration/edit_lock.acquire", json=request)
    ).status_code == 403
    assert (
        await alice.post("/api/collaboration/edit_lock.release", json=request)
    ).status_code == 200
    # A heartbeat after release cannot reacquire the lease.
    assert (await alice.post("/api/collaboration/edit_lock.heartbeat", json=request)).json() == {
        "renewed": False
    }
    assert (
        await bob.post(
            "/api/collaboration/edit_lock.acquire", json={**request, "leaseId": "bob-editor"}
        )
    ).json()["acquired"]


async def test_team_cannot_lock_a_personal_resource_even_if_the_body_claims_that_owner(editors):
    team_id, clients, redis = editors
    alice = clients["alice"]
    saved = await alice.post(
        "/api/resources/resource.save",
        json={
            "category": "conditions",
            "type": "router_boolean",
            "name": "Personal",
            "config": {"boolean_value": True},
        },
    )
    response = await alice.post(
        "/api/collaboration/edit_lock.acquire",
        json={
            "teamId": team_id,
            "entityKind": "resource",
            "entityId": saved.json()["rid"],
            "userId": "alice",
        },
    )
    assert response.status_code in (403, 404), response.text
    assert not [key async for key in redis.scan_iter(match=f"mas:collab:editlock:team:{team_id}:*")]
