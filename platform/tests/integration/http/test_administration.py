"""Retained configuration/consent flows use native human authority and durable stores."""

import asyncio
import os
import shutil
from contextlib import AsyncExitStack

from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.server import api_process
from support.ui_clients import run_contracts

from flareward.services.connections.adapters.redis import owned_redis


async def test_configuration_authority_conflict_validation_and_consent_restart(
    mongo_database, redis_uri, tmp_path, request
):
    settings = session_settings(mongo_database.name, redis_uri).model_copy(
        update={"admin_config_database": mongo_database.name, "admin_allowed_users": ("alice",)}
    )
    async with AsyncExitStack() as stack:
        redis = await stack.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        headers = {}
        for user in ("alice", "bob"):
            cookie = await stack.enter_async_context(
                authenticated_cookie(redis, user, settings.secret_key.get_secret_value())
            )
            headers[user] = {"Cookie": "session=" + cookie}
        async with api_process(settings, tmp_path / "administration.log") as http:
            endpoint = "/api/administration/configuration"
            assert (await http.get(endpoint)).status_code == 401
            assert (await http.get(endpoint, headers=headers["bob"])).status_code == 403
            assert (
                await http.get("/api/administration/access?username=alice", headers=headers["bob"])
            ).json() == {"is_admin": False}
            response = await http.get(endpoint, headers=headers["alice"])
            assert response.status_code == 200, response.text
            assert response.json()["categories"][0]["sections"][0]["revision"] == 0
            body = {
                "section": "admin_users",
                "values": {"admin_usernames": ["alice", "bob"]},
                "expected_revision": 0,
            }
            responses = await asyncio.gather(
                *(http.put(endpoint, headers=headers["alice"], json=body) for _ in range(2))
            )
            assert sorted(item.status_code for item in responses) == [200, 409]
            assert (
                await http.get("/api/administration/access", headers=headers["bob"])
            ).json() == {"is_admin": True}
            invalid = {
                **body,
                "expected_revision": 1,
                "values": {"admin_usernames": ["alice"], "unexpected": "private-sentinel"},
            }
            denied = await http.put(endpoint, headers=headers["alice"], json=invalid)
            assert denied.status_code == 422 and "private-sentinel" not in denied.text
            missing = await http.put(
                endpoint, headers=headers["alice"], json={**body, "section": "missing"}
            )
            assert missing.status_code == 404
            consent = "/api/consents/ai-transparency"
            assert (await http.get(consent, headers=headers["alice"])).json()["approved"] is False
            assert (await http.post(consent, headers=headers["alice"])).status_code == 200
            assert (await http.post(consent, headers=headers["alice"])).status_code == 200
            assert (await http.get(consent, headers=headers["bob"])).json()["approved"] is False
            assert (
                await http.get(
                    consent, headers={**headers["alice"], "Authorization": "Bearer invalid"}
                )
            ).status_code == 401
        async with api_process(settings, tmp_path / "administration-restarted.log") as http:
            response = await http.get("/api/administration/configuration", headers=headers["bob"])
            assert response.status_code == 200, response.text
            assert response.json()["categories"][0]["sections"][0]["revision"] == 1
            assert (
                await http.get("/api/consents/ai-transparency", headers=headers["alice"])
            ).json()["approved"] is True
            if request.config.getoption("--ui-clients"):
                node = shutil.which("node")
                assert node is not None
                output = await run_contracts(
                    node,
                    "administration",
                    {
                        **os.environ,
                        "FLAREWARD_TEST_UI_API_URL": str(http.base_url).rstrip("/") + "/api",
                        "FLAREWARD_TEST_UI_ADMIN_COOKIE": headers["alice"]["Cookie"],
                    },
                )
                assert "Administration and consent production clients passed" in output
        assert await mongo_database.human_consents.count_documents({}) == 1
