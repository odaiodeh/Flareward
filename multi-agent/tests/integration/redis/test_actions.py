"""Actual native action routes, signed-cookie identity, team membership and encrypted stores."""

import os

import pytest
from mas.application.actions.service import ActionsService
from outbound.crypto import FieldCipher
from support.action_scenarios import FailingAction, IdentityAction, InvalidOutputAction
from support.team_http import team_api


def redis_uri():
    uri = os.environ.get("UNIFAI_TEST_REDIS_URI")
    if not uri:
        pytest.skip("Set UNIFAI_TEST_REDIS_URI for authenticated action contracts")
    return uri


async def test_action_transport_trusts_authenticated_identity_and_preserves_safe_failures(
    secret_settings,
):
    actions = ActionsService((IdentityAction(), FailingAction(), InvalidOutputAction()))
    async with team_api(secret_settings, redis_uri(), actions=actions) as team:
        alice = team.clients["alice"]
        assert (
            await alice.get("/api/actions/actions.list", headers={"Cookie": ""})
        ).status_code == 401
        metadata = await alice.get(
            "/api/actions/actions.list", params={"type": "fixture", "tags": "identity"}
        )
        assert metadata.status_code == 200 and metadata.json()["total_actions"] == 3
        assert (await alice.get("/api/actions/actions.list", params={"type": "other"})).json()[
            "actions"
        ] == []
        body = {
            "uid": "fixture.identity",
            "teamId": team.team_id,
            "userId": "bob",
            "inputData": {"user_id": "bob", "count": 7},
            "context": {"credential_user_id": "bob", "owner": "other"},
        }
        result = await alice.post("/api/actions/action.execute", json=body)
        assert result.status_code == 200, result.text
        assert result.json() == {
            "success": True,
            "message": "Context checked",
            "actor": "alice",
            "owner": team.team_id,
            "count": 7,
        }
        assert (
            await team.clients["mallory"].post("/api/actions/action.execute", json=body)
        ).status_code == 403
        for uid, arguments, status in (
            ("missing", {}, 404),
            ("fixture.identity", {"count": "private-input"}, 422),
            ("fixture.failure", {}, 502),
            ("fixture.invalid-output", {}, 502),
        ):
            failed = await alice.post(
                "/api/actions/action.execute", json={"uid": uid, "inputData": arguments}
            )
            assert failed.status_code == status, failed.text
            assert "private" not in failed.text


async def test_configured_model_actions_use_real_async_settings_and_existing_schemas(
    secret_settings, mongo_database
):
    await mongo_database.admin_config.insert_one(
        {
            "key": "openai_model_capabilities",
            "value": {
                "capabilities": {
                    "fixture": {"reasoning": ["low"]},
                    "fixture-mini": {"reasoning": ["minimal"]},
                }
            },
        }
    )
    settings = secret_settings.model_copy(update={"admin_config_database": mongo_database.name})
    async with team_api(settings, redis_uri()) as team:
        alice = team.clients["alice"]
        metadata = await alice.get(
            "/api/actions/actions.list", params={"category": "llms", "type": "openai"}
        )
        assert metadata.status_code == 200
        assert {item["uid"] for item in metadata.json()["actions"]} == {
            "openai.get_models",
            "openai.get_reasoning_levels",
        }
        models = await alice.post(
            "/api/actions/action.execute",
            json={"uid": "openai.get_models", "inputData": {}, "userId": "ignored"},
        )
        assert models.status_code == 200 and models.json()["models"] == [
            "fixture",
            "fixture-mini",
        ], models.text
        levels = await alice.post(
            "/api/actions/action.execute",
            json={
                "uid": "openai.get_reasoning_levels",
                "inputData": {"model_name": "fixture-mini-new"},
            },
        )
        assert levels.json()["reasoning_levels"] == ["minimal"] and levels.json()["model_found"]
        empty = await alice.get(
            "/api/actions/actions.list", params={"category": "nodes", "type": "mock_agent_node"}
        )
        assert empty.status_code == 200 and empty.json()["actions"] == []


async def test_credential_actions_never_use_request_authored_users_or_return_raw_tokens(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"credentials": "mongo"})
    token, server = "private-action-credential", "https://action-fixture.invalid"
    async with team_api(settings, redis_uri()) as team:
        alice, bob = team.clients["alice"], team.clients["bob"]
        stored = await alice.post(
            "/api/actions/action.execute",
            json={
                "uid": "auth.store_credential",
                "inputData": {
                    "user_id": "bob",
                    "server_url": server,
                    "credential": token,
                    "scheme_type": "api_key",
                },
            },
        )
        assert stored.status_code == 200 and stored.json()["authenticated"], stored.text
        document = await mongo_database.credentials.find_one({"user_id": "alice"})
        assert (
            document
            and token not in str(document)
            and not await mongo_database.credentials.find_one({"user_id": "bob"})
        )
        discovered = await alice.post(
            "/api/actions/action.execute",
            json={
                "uid": "auth.discovery",
                "inputData": {"user_id": "bob", "server_identifier": server},
            },
        )
        assert discovered.json()["authenticated"], discovered.text
        sealed = discovered.json()["form_updates"]["credential_token"]
        assert (
            FieldCipher(settings.credential_encryption_key.get_secret_value()).decrypt(sealed)
            == token
        )
        assert token not in stored.text + discovered.text
        for client, user in ((bob, "alice"), (alice, "bob")):
            result = await client.post(
                "/api/actions/action.execute",
                json={
                    "uid": "auth.sign_out",
                    "inputData": {"user_id": user, "server_identifier": server},
                },
            )
            assert result.status_code == 200 and result.json()["signed_out"], result.text
            count = await mongo_database.credentials.count_documents({"user_id": "alice"})
            assert count == (1 if client is bob else 0)
