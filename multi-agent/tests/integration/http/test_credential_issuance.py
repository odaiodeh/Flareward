"""Human-bound keyed issuance survives an actual API restart and native root cleanup."""

import asyncio
import json

import pytest
from cryptography.fernet import Fernet
from mas.core.identity import Identity
from mas.domain.programs.models import ApplicationDefinition, ProgramDefinition
from outbound.redis_client import owned_redis
from pydantic import SecretStr
from support.http_programs import publish_program
from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.review_api import review_settings
from support.server import api_process
from support.verification import verification_policy

from config.platform_settings import VerificationAuthorityConfig


@pytest.mark.parametrize("purpose", ["review", "verification"])
async def test_keyed_human_issuance_recovers_after_api_restart_and_retires_with_native_root(
    mongo_database, redis_uri, tmp_path, purpose
):
    owner = Identity.user("issuance-owner")
    settings = (
        review_settings(owner, mongo_database.name, redis_uri)
        if purpose == "review"
        else (
            session_settings(mongo_database.name, redis_uri).model_copy(
                update={
                    "verification_enabled": True,
                    "verification_policies": {"release@1": verification_policy(owner)},
                    "verification_authorities": {
                        name: VerificationAuthorityConfig(
                            credential_sha256=digest * 64, owners=(owner,)
                        )
                        for name, digest in (("ci", "a"), ("scanner", "b"))
                    },
                }
            )
        )
    )
    settings = settings.model_copy(
        update={
            "recoverable_credential_issuance": True,
            "credential_encryption_key": SecretStr(Fernet.generate_key().decode()),
            "workflow_credential_directory": tmp_path / "managed-workflow-access",
            "reconcile_interval": 0.05,
        }
    )
    path = f"/api/{purpose}-access"
    body = {
        "ttl_seconds": 60,
        "renewable_for_seconds": 180,
        "scope": {
            "root_execution_id": "recoverable-root",
            "policies": ["release@1"],
            "actions": ["open", "read", "close"]
            if purpose == "review"
            else ["create", "read", "cancel"],
        },
    }
    async with owned_redis(redis_uri, decode_responses=True) as redis:
        async with authenticated_cookie(
            redis, owner.id, settings.secret_key.get_secret_value()
        ) as cookie:
            human = {"Cookie": "session=" + cookie}
            keyed = {**human, "Idempotency-Key": "original-issuance"}
            first_log, second_log = tmp_path / "first-api.log", tmp_path / "second-api.log"
            async with api_process(settings, first_log) as http:
                issued = await http.post(path, headers=keyed, json=body)
                assert issued.status_code == 201
                original = issued.json()
                assert issued.headers["Cache-Control"] == "no-store"
                document = await mongo_database.workflow_credential_material.find_one({})
                assert original["credential"] not in json.dumps(document)
                assert len(list(settings.workflow_credential_directory.rglob("*.json"))) == 1
                # A workflow bearer cannot obtain human issuance authority through
                # an accompanying valid human cookie.
                denied = await http.post(
                    path,
                    headers={**keyed, "Authorization": "Bearer " + original["credential"]},
                    json=body,
                )
                assert denied.status_code == 401
            async with api_process(settings, second_log) as http:
                recovered = await http.post(path, headers=keyed, json=body)
                assert recovered.status_code == 201
                assert recovered.json() == original
                conflict = await http.post(path, headers=keyed, json={**body, "ttl_seconds": 61})
                assert conflict.status_code == 409
                assert original["credential"] not in conflict.text
                assert await mongo_database.workflow_credential_material.count_documents({}) == 1
                reference = await publish_program(
                    http,
                    ProgramDefinition(
                        program_id="waiting-root",
                        name="Waiting root",
                        owner=owner,
                        implementation=ApplicationDefinition(
                            implementation="wait",
                            version="1",
                            config={"channel": "human-signal", "timeout_seconds": 60},
                        ),
                    ),
                    headers=human,
                )
                started = await http.post(
                    "/api/executions",
                    headers=human,
                    json={
                        "execution_id": body["scope"]["root_execution_id"],
                        "program": reference.model_dump(mode="json"),
                        "inputs": {},
                    },
                )
                assert started.status_code == 202, started.text
                bearer = {"Authorization": "Bearer " + original["credential"]}
                assert (await http.get(path + "/self", headers=bearer)).status_code == 200
                commands = [
                    ("POST", path, body),
                    ("DELETE", path + "/" + original["grant"]["grant_id"], None),
                ]
                if purpose == "verification":
                    commands.append(("GET", path, None))
                for method, target, content in commands:
                    denied = await http.request(
                        method, target, headers={**human, **bearer}, json=content
                    )
                    assert denied.status_code == 401
                if purpose == "verification":
                    listed = await http.get(path, headers=human)
                    assert listed.status_code == 200 and len(listed.json()) == 1
                cancelled = await http.post(
                    "/api/executions/recoverable-root/cancel", headers=human
                )
                assert cancelled.status_code == 202, cancelled.text
                result = await http.get("/api/executions/recoverable-root/result", headers=human)
                assert result.status_code == 200 and result.json()["phase"] == "cancelled"
                async with asyncio.timeout(10):
                    while True:
                        retired = await mongo_database.workflow_credential_material.find_one({})
                        if retired["retired"] and not retired["cleanup_pending"]:
                            break
                        await asyncio.sleep(0.05)
                assert "credential" not in retired and retired["data"] == document["data"]
                assert not list(settings.workflow_credential_directory.rglob("*.json"))
                assert (await http.get(path + "/self", headers=bearer)).status_code == 401
                assert (await http.post(path, headers=keyed, json=body)).status_code == 403
                assert (
                    await http.delete(path + "/" + original["grant"]["grant_id"], headers=human)
                ).status_code == 204
            assert original["credential"] not in first_log.read_text() + second_log.read_text()
