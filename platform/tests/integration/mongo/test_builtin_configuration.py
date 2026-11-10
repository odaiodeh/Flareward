"""Native caller overlays remain compatible with library resolution and legacy writers."""

import asyncio
import os

from pymongo import MongoClient
from support.blueprint_http import library_api
from support.blueprints import external_blueprint

from lumora.resources.adapters.mongo.builtin_configuration_repository import (
    MongoBuiltinConfigurationRepository,
)
from lumora.resources.adapters.mongo.builtin_user_config_repository import (
    MongoBuiltinUserConfigRepository,
)
from lumora.resources.adapters.mongo.configuration_secrets import MongoConfigurationSecrets
from lumora.resources.domain.builtins import (
    BuiltinResourceDescriptor,
    BuiltinUserConfig,
    identity_to_key,
)
from lumora.services.auth.adapters.crypto import FieldCipher
from lumora.services.identity.domain import Identity


async def test_builtin_http_configuration_is_owner_scoped_versioned_and_snapshotted(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    cipher = FieldCipher(settings.credential_encryption_key.get_secret_value())
    async with library_api(settings, Identity.user("admin")) as http:
        response = await http.post(
            "/api/resources",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Shared",
                "config": {
                    "type": "mock",
                    "base_url": "http://unused.invalid",
                    "api_key": "admin-private",
                },
            },
        )
        assert response.status_code == 201, response.text
        rid = response.json()["rid"]
    descriptor = BuiltinResourceDescriptor(rid=rid, visibility="public")
    await mongo_database.builtin_resource_descriptors.insert_one(
        {"_id": rid, **descriptor.model_dump(mode="json")}
    )
    store = MongoConfigurationSecrets(mongo_database, cipher)
    for owner in (Identity.user("same-id"), Identity.team("same-id")):
        token = owner.type.value + "-caller-private"
        async with library_api(settings, owner) as http:
            path = f"/api/resources/{rid}/configuration"
            assert (await http.get(path)).json() is None
            assert not (await http.get(f"/api/resources/{rid}")).json()["user_configured"]
            responses = await asyncio.gather(
                *[
                    http.patch(path, json={"config": {"api_key": token}, "expected_version": 0})
                    for _ in range(5)
                ]
            )
            assert [response.status_code for response in responses].count(200) == 1
            assert [response.status_code for response in responses].count(409) == 4
            configured = (await http.get(path)).json()
            assert configured["version"] == 1
            assert configured["identity_key"] == identity_to_key(owner)
            assert cipher.decrypt(configured["fields"]["api_key"]) == token
            assert token not in str(configured)
            listed = (await http.get("/api/resources?ownership=builtin")).json()["resources"]
            assert listed[0]["user_configured"]
            assert listed[0]["cfg_dict"]["api_key"] == configured["fields"]["api_key"]
            invalid = await http.patch(path, json={"config": {"base_url": "private-invalid"}})
            assert invalid.status_code == 422 and "private-invalid" not in invalid.text
            invalid = await http.patch(
                path, json={"config": {"api_key": {"invalid": "private-invalid"}}}
            )
            assert invalid.status_code == 422 and "private-invalid" not in invalid.text
            node = await http.post(
                "/api/resources",
                json={
                    "category": "nodes",
                    "type": "mock_agent_node",
                    "name": "Personal agent",
                    "config": {"type": "mock_agent_node", "llm": "$ref:" + rid},
                },
            )
            assert node.status_code == 201, node.text
            blueprint = await http.post(
                "/api/blueprints",
                json={"spec": external_blueprint(node.json()["rid"]).model_dump(mode="json")},
            )
            assert blueprint.status_code == 201, blueprint.text
            program = owner.type.value + "-overlay"
            imported = await http.put(
                f"/api/programs/{program}/blueprint",
                json={"blueprint_id": blueprint.json()["blueprint_id"]},
            )
            assert imported.status_code == 200, imported.text
            model = next(
                resource
                for resource in imported.json()["definition"]["implementation"]["resources"]
                if resource["key"]["rid"] == rid
            )
            reference = model["config"]["api_key"]
            assert (await store.get(owner, reference)).get_secret_value() == token
            assert (
                await http.post(f"/api/programs/{program}/revisions", json={"expected_version": 1})
            ).status_code == 201
            assert (await http.delete(path + "?expected_version=0")).status_code == 409
            assert (await http.delete(path + "?expected_version=1")).status_code == 204
            cleared = (await http.get(path)).json()
            assert cleared["version"] == 2 and cleared["fields"] == {}
            assert not (await http.get(f"/api/resources/{rid}")).json()["user_configured"]
            assert (
                await http.patch(path, json={"config": {"api_key": "stale"}, "expected_version": 1})
            ).status_code == 409
            edited = await http.patch(
                path, json={"config": {"api_key": "changed-private"}, "expected_version": 2}
            )
            assert edited.status_code == 200 and edited.json()["version"] == 3, edited.text
            assert (await store.get(owner, reference)).get_secret_value() == token
    saved = await mongo_database.builtin_user_configs.find().to_list()
    assert len(saved) == 2 and all(row["version"] == 3 for row in saved)
    assert "changed-private" not in str(saved)
    base = await mongo_database.resources.find_one({"_id": rid})
    assert cipher.decrypt(base["cfg_dict"]["api_key"]) == "admin-private"
    await mongo_database.builtin_resource_descriptors.update_one(
        {"_id": rid}, {"$set": {"visibility": "draft"}}
    )
    async with library_api(settings, Identity.user("same-id")) as http:
        assert (await http.get(path)).status_code == 404
        assert (await http.patch(path, json={"config": {"api_key": "private"}})).status_code == 404
        assert (await http.delete(path)).status_code == 404


async def test_builtin_configuration_cas_handles_versionless_records_and_fences_legacy_writes(
    mongo_database,
):
    repository = MongoBuiltinConfigurationRepository(mongo_database.builtin_user_configs)
    await repository.initialize()
    previous = BuiltinUserConfig(
        resource_id="builtin", identity_key="user:owner", fields={"label": "Old"}
    )
    await mongo_database.builtin_user_configs.insert_one(
        {"_id": previous.config_id, **previous.model_dump(mode="json", exclude={"version"})}
    )
    original = await repository.get("builtin", "user:owner")
    assert original.version == 0
    updated = original.model_copy(update={"version": 1, "fields": {"label": "Native"}})
    assert await repository.replace(original, updated)

    def legacy_edit():
        with MongoClient(os.environ["LUMORA_TEST_MONGO_URI"]) as client:
            legacy = MongoBuiltinUserConfigRepository(database=client[mongo_database.name])
            legacy.close()
            current = legacy.get("builtin", "user:owner")
            current.fields["label"] = "Legacy edited"
            legacy.save(current)
            assert current.version == 2

    await asyncio.to_thread(legacy_edit)
    assert not await repository.replace(updated, updated.model_copy(update={"version": 2}))
    current = await repository.get("builtin", "user:owner")
    assert current.version == 2 and current.fields == {"label": "Legacy edited"}
    assert await repository.list("team:owner") == []
