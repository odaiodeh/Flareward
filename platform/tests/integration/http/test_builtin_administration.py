"""Signed humans use actual curated HTTP/Mongo/Redis administration and production UI clients."""

import os
import shutil
from contextlib import AsyncExitStack

from cryptography.fernet import Fernet
from pydantic import SecretStr
from support.identity import authenticated_cookie
from support.native_settings import session_settings
from support.server import api_process
from support.ui_clients import run_contracts

from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.connections.adapters.redis import owned_redis


async def test_curated_library_native_authority_transactions_leases_and_clients(
    transaction_database, redis_uri, tmp_path, request
):
    settings = session_settings(transaction_database.name, redis_uri).model_copy(
        update={
            "mongo_uri": SecretStr(os.environ["LUMORA_TEST_MONGO_TRANSACTION_URI"]),
            "library": True,
            "edit_locks": True,
            "admin_config_database": transaction_database.name,
            "admin_allowed_users": ("curator", "other-admin"),
            "credential_encryption_key": SecretStr(Fernet.generate_key().decode()),
        }
    )
    cipher = FieldCipher(settings.credential_encryption_key.get_secret_value())
    async with AsyncExitStack() as stack:
        redis = await stack.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookies = {}
        for name in ("curator", "other-admin", "reader"):
            cookies[name] = await stack.enter_async_context(
                authenticated_cookie(redis, name, settings.secret_key.get_secret_value())
            )
        http = await stack.enter_async_context(
            api_process(
                settings, tmp_path / "curated.log", factory="support.builtin_http:create_app"
            )
        )
        admin = {"Cookie": "session=" + cookies["curator"]}
        other = {"Cookie": "session=" + cookies["other-admin"]}
        reader = {"Cookie": "session=" + cookies["reader"]}
        prefix = "/api/administration/resources"
        assert (await http.get(prefix)).status_code == 401
        assert (await http.get(prefix + "?userId=curator", headers=reader)).status_code == 403
        assert (
            await http.get(prefix, headers={**admin, "Authorization": "Bearer invalid"})
        ).status_code == 401
        created = []
        for name, type_key, config, public in (
            ("leaf", "platform_secret_tool", {"api_key": "private-curated-key"}, False),
            ("middle", "platform_dependency", {}, False),
            ("root", "platform_dependency", {}, True),
        ):
            if created:
                config = {"dependency": "$ref:" + created[-1]["rid"]}
            response = await http.post(
                prefix,
                headers=admin,
                json={
                    "category": "tools",
                    "type": type_key,
                    "name": name,
                    "config": config,
                    "public": public,
                },
            )
            assert response.status_code == 201, response.text
            assert "private-curated-key" not in response.text
            created.append(response.json())
        leaf, middle, root = created
        assert {row["rid"] for row in root["cascaded_resources"]} == {leaf["rid"], middle["rid"]}
        saved = await transaction_database.resources.find_one({"_id": leaf["rid"]})
        assert cipher.decrypt(saved["cfg_dict"]["api_key"]) == "private-curated-key"
        public_leaf = await http.get("/api/resources/" + leaf["rid"], headers=reader)
        assert (
            public_leaf.status_code == 200 and saved["cfg_dict"]["api_key"] not in public_leaf.text
        )
        leaf = (await http.get(prefix + "/" + leaf["rid"], headers=admin)).json()
        denied = await http.put(
            prefix + "/" + leaf["rid"],
            headers=admin,
            json={"expected_version": leaf["version"], "public": False},
        )
        assert denied.status_code == 409, denied.text
        lease = prefix + "/" + root["rid"] + "/edit-lease"
        assert (await http.post(lease, headers=admin)).json()["acquired"] is True
        busy = await http.post(lease, headers=other)
        assert busy.json()["acquired"] is False and busy.json()["lockedBy"]["userId"] == "curator"
        assert (
            await http.put(
                prefix + "/" + root["rid"],
                headers=other,
                json={"expected_version": root["version"], "name": "blocked"},
            )
        ).status_code == 409
        await http.delete(lease, headers=other)
        assert (await http.put(lease, headers=admin)).json()["renewed"] is True
        updated = await http.put(
            prefix + "/" + root["rid"],
            headers=admin,
            json={"expected_version": root["version"], "name": "Revised root"},
        )
        assert updated.status_code == 200 and updated.json()["version"] == 2, updated.text
        assert (
            await http.put(
                prefix + "/" + root["rid"],
                headers=admin,
                json={"expected_version": root["version"], "name": "stale"},
            )
        ).status_code == 409
        assert (
            await http.delete(
                prefix + "/" + leaf["rid"],
                headers=admin,
                params={"expected_version": leaf["version"]},
            )
        ).status_code == 409
        await http.delete(lease, headers=admin)
        if request.config.getoption("--ui-clients"):
            node = shutil.which("node")
            assert node is not None
            output = await run_contracts(
                node,
                "builtins",
                {
                    **os.environ,
                    "LUMORA_TEST_UI_API_URL": str(http.base_url).rstrip("/") + "/api",
                    "LUMORA_TEST_UI_ADMIN_COOKIE": admin["Cookie"],
                    "LUMORA_TEST_UI_OWNER_COOKIE": reader["Cookie"],
                    "LUMORA_TEST_UI_ROOT_RESOURCE": root["rid"],
                },
            )
            assert "Curated library production clients passed" in output
        await transaction_database.admin_config.insert_one(
            {"key": "admin_users", "value": {"admin_usernames": []}}
        )
        assert (await http.get(prefix, headers=admin)).status_code == 403
        assert "private-curated-key" not in (tmp_path / "curated.log").read_text()
