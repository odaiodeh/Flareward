"""Native admin base probes preserve private drafts, owner overlays and actual human credentials."""

import asyncio
import hashlib
import os
import shutil
from contextlib import AsyncExitStack

from cryptography.fernet import Fernet
from mas.core.auth.credentials.models import StoredCredential
from outbound.redis_client import owned_redis
from pydantic import SecretStr
from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.server import api_process
from support.ui_clients import run_contracts

from bootstrap.credentials import receiver_auth
from config.receiver_settings import CredentialBackend


async def test_native_curated_inspection_distinguishes_base_and_overlay_views(
    transaction_database, redis_uri, tmp_path, request
):
    settings = session_settings(transaction_database.name, redis_uri).model_copy(
        update={
            "mongo_uri": SecretStr(os.environ["UNIFAI_TEST_MONGO_TRANSACTION_URI"]),
            "library": True,
            "edit_locks": True,
            "credentials": CredentialBackend.MONGO,
            "admin_config_database": transaction_database.name,
            "admin_allowed_users": ("curator",),
            "credential_encryption_key": SecretStr(Fernet.generate_key().decode()),
        }
    )
    token = "curated-probe-base-private"
    async with AsyncExitStack() as stack:
        auth = await stack.enter_async_context(receiver_auth(settings))
        await asyncio.to_thread(
            auth.save_credential,
            StoredCredential(
                user_id="curator",
                server_identifier="inspection",
                scheme_type="api_key",
                access_token="probe-server-private",
            ),
        )
        redis = await stack.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookies = {}
        for name in ("curator", "reader"):
            cookies[name] = await stack.enter_async_context(
                authenticated_cookie(redis, name, settings.secret_key.get_secret_value())
            )
        http = await stack.enter_async_context(
            api_process(
                settings,
                tmp_path / "inspection.log",
                factory="support.curated_inspection_http:create_app",
            )
        )
        admin, reader = ({"Cookie": "session=" + cookies[name]} for name in ("curator", "reader"))
        prefix = "/api/administration/resources"
        model_response = await http.post(
            prefix,
            headers=admin,
            json={
                "category": "llms",
                "type": "mock",
                "name": "Private curated provider",
                "config": {
                    "api_key": token,
                    "base_url": "http://unused.invalid",
                    "expected_digest": hashlib.sha256(token.encode()).hexdigest(),
                    "expected_owner": "curator",
                    "expected_human": "curator",
                },
            },
        )
        assert model_response.status_code == 201, model_response.text
        model = model_response.json()
        node_response = await http.post(
            prefix,
            headers=admin,
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "name": "Private curated agent",
                "config": {"llm": "$ref:" + model["rid"]},
            },
        )
        assert node_response.status_code == 201, node_response.text
        node = node_response.json()
        probe = prefix + "/validation"
        body = {"resource_ids": [node["rid"]]}
        assert (await http.post(probe, json=body)).status_code == 401
        assert (
            await http.post(probe + "?userId=curator", headers=reader, json=body)
        ).status_code == 403
        assert (
            await http.post(probe, headers={**admin, "Authorization": "Bearer invalid"}, json=body)
        ).status_code == 401
        response = await http.post(probe, headers=admin, json=body)
        assert response.status_code == 200, response.text
        report = response.json()
        assert report["mode"] == "curated_base" and report["observed_at"]
        assert report["results"][0]["is_valid"]
        assert report["results"][0]["dependency_results"][model["rid"]]["is_valid"]
        owner = await http.post("/api/resources/validation", headers=admin, json=body)
        assert owner.status_code == 200 and not owner.json()[0]["is_valid"]
        assert (
            await http.post(
                "/api/resources/validation", headers=admin, json={**body, "mode": "curated_base"}
            )
        ).status_code == 422
        inline = {
            "category": "nodes",
            "type": "mock_agent_node",
            "config": {"llm": "$ref:" + model["rid"]},
        }
        response = await http.post(prefix + "/configuration/validation", headers=admin, json=inline)
        assert response.status_code == 200 and response.json()["results"][0]["is_valid"], (
            response.text
        )
        assert (
            await http.post("/api/resources/configuration/validation", headers=admin, json=inline)
        ).status_code == 404
        published = await http.put(
            prefix + "/" + node["rid"],
            headers=admin,
            json={"expected_version": node["version"], "public": True},
        )
        assert published.status_code == 200, published.text
        overlay = await http.patch(
            "/api/resources/" + model["rid"] + "/configuration",
            headers=admin,
            json={"config": {"api_key": "personal-overlay-private"}},
        )
        assert overlay.status_code == 200, overlay.text
        owner = await http.post("/api/resources/validation", headers=admin, json=body)
        assert owner.status_code == 200 and not owner.json()[0]["is_valid"]
        response = await http.post(probe, headers=admin, json=body)
        assert response.status_code == 200 and response.json()["results"][0]["is_valid"]
        if request.config.getoption("--ui-clients"):
            executable = shutil.which("node")
            assert executable is not None
            output = await run_contracts(
                executable,
                "curated_inspection",
                {
                    **os.environ,
                    "UNIFAI_TEST_UI_API_URL": str(http.base_url).rstrip("/") + "/api",
                    "UNIFAI_TEST_UI_ADMIN_COOKIE": admin["Cookie"],
                    "UNIFAI_TEST_UI_OWNER_COOKIE": reader["Cookie"],
                    "UNIFAI_TEST_UI_CURATED_RESOURCE": node["rid"],
                },
            )
            assert "Curated inspection production clients passed" in output
        changed = (await http.get(prefix + "/" + model["rid"], headers=admin)).json()
        config = {**changed["cfg_dict"], "fail": True}
        assert (
            await http.put(
                prefix + "/" + model["rid"],
                headers=admin,
                json={"expected_version": changed["version"], "config": config},
            )
        ).status_code == 200
        failed = await http.post(probe, headers=admin, json=body)
        assert failed.status_code == 503, failed.text
        assert all(
            secret not in failed.text
            for secret in (token, "personal-overlay-private", "probe-server-private")
        )
        await transaction_database.admin_config.insert_one(
            {"key": "admin_users", "value": {"admin_usernames": []}}
        )
        assert (await http.post(probe, headers=admin, json=body)).status_code == 403
        assert token not in (tmp_path / "inspection.log").read_text()
