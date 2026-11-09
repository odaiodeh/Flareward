"""Native HTTP resources share encrypted library data and optimistic edit semantics."""

import asyncio
import os

import pytest
from pymongo import MongoClient
from support.blueprint_http import library_api
from support.blueprints import external_blueprint

from flareward.programs.graph.state.graph_state import GraphState
from flareward.programs.templates.adapters.mongo.blueprint_repository import (
    MongoBlueprintRepository,
)
from flareward.programs.templates.adapters.mongo.blueprint_usage import MongoBlueprintUsage
from flareward.resources.adapters.mongo.resource_authoring_repository import (
    MongoResourceAuthoringRepository,
)
from flareward.resources.adapters.mongo.resource_repository import MongoResourceRepository
from flareward.resources.domain.builtins import BuiltinResourceDescriptor
from flareward.resources.domain.models import Resource
from flareward.resources.errors import ResourceInUseError
from flareward.resources.registry import ResourcesRegistry
from flareward.services.auth.adapters.crypto import FieldCipher
from flareward.services.identity.domain import Identity


def model_request(token="EMPTY", *, name="Model"):
    return {
        "category": "llms",
        "type": "mock",
        "name": name,
        "config": {"type": "mock", "base_url": "http://unused.invalid", "api_key": token},
    }


async def test_resource_http_encryption_roundtrip_concurrent_edits_and_safe_errors(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    cipher = FieldCipher(settings.credential_encryption_key.get_secret_value())
    async with library_api(settings, Identity.user("owner")) as http:
        schema = await http.get("/api/resources/schema/llms/mock")
        assert schema.status_code == 200 and "api_key" in schema.json()["properties"]
        created = await http.post("/api/resources", json=model_request("resource-private"))
        assert created.status_code == 201 and "resource-private" not in created.text, created.text
        resource = created.json()
        rid = resource["rid"]
        saved = await mongo_database.resources.find_one({"_id": rid})
        assert cipher.decrypt(saved["cfg_dict"]["api_key"]) == "resource-private"
        assert saved["version"] == 1
        assert (await http.get(f"/api/resources/{rid}")).json() == resource
        assert (await http.post("/api/resources", json=model_request())).status_code == 409
        edits = await asyncio.gather(
            *[
                http.put(
                    f"/api/resources/{rid}",
                    json={
                        "config": resource["cfg_dict"],
                        "name": str(number),
                        "expected_version": 1,
                    },
                )
                for number in range(5)
            ]
        )
        assert [response.status_code for response in edits].count(200) == 1
        assert [response.status_code for response in edits].count(409) == 4
        current = (await http.get(f"/api/resources/{rid}")).json()
        assert current["version"] == 2
        assert cipher.decrypt(current["cfg_dict"]["api_key"]) == "resource-private"
        invalid = await http.post(
            "/api/resources", json=model_request({"invalid": "resource-private"})
        )
        assert invalid.status_code == 422 and "resource-private" not in invalid.text
        corrupt = await http.post("/api/resources", json=model_request("gAAAAAB-invalid-private"))
        assert corrupt.status_code == 422 and "gAAAAAB-invalid-private" not in corrupt.text
        assert (await http.get("/api/resources?offset=-1")).status_code == 422
        assert (await http.delete(f"/api/resources/{rid}?expected_version=1")).status_code == 409
        assert (await http.delete(f"/api/resources/{rid}?expected_version=2")).status_code == 204


async def test_resource_visibility_separates_users_teams_and_public_builtins(
    secret_settings, mongo_database
):
    cipher = FieldCipher(secret_settings.credential_encryption_key.get_secret_value())
    for rid, owner, visibility in (
        ("own", Identity.user("same-id"), None),
        ("team", Identity.team("same-id"), None),
        ("foreign", Identity.user("other"), None),
        ("public", Identity.user("admin"), "public"),
        ("draft", Identity.user("admin"), "draft"),
    ):
        resource = Resource(
            rid=rid,
            identity=owner,
            category="llms",
            type="mock",
            name=rid,
            cfg_dict={**model_request()["config"], "api_key": cipher.encrypt("shared-private")},
        )
        await mongo_database.resources.insert_one({"_id": rid, **resource.model_dump(mode="json")})
        if visibility:
            descriptor = BuiltinResourceDescriptor(rid=rid, visibility=visibility)
            await mongo_database.builtin_resource_descriptors.insert_one(
                {"_id": rid, **descriptor.model_dump(mode="json")}
            )
    settings = secret_settings.model_copy(update={"library": True})
    for caller, own in ((Identity.user("same-id"), "own"), (Identity.team("same-id"), "team")):
        async with library_api(settings, caller) as http:
            listed = await http.get("/api/resources?category=llms&type=mock")
            assert listed.status_code == 200, listed.text
            assert {item["rid"] for item in listed.json()["resources"]} == {own, "public"}
            assert listed.json()["total"] == 2
            for ownership, expected in (("custom", own), ("builtin", "public")):
                filtered = await http.get(f"/api/resources?ownership={ownership}&limit=1")
                assert filtered.json()["total"] == 1
                assert filtered.json()["resources"][0]["rid"] == expected
            public = await http.get("/api/resources/public")
            assert public.json()["cfg_dict"]["api_key"] == ""
            assert "shared-private" not in public.text and "gAAAAAB" not in public.text
            assert (await http.get("/api/resources/foreign")).status_code == 404
            assert (await http.get("/api/resources/draft")).status_code == 404
            assert (await http.delete("/api/resources/foreign")).status_code == 403
            assert (
                await http.put("/api/resources/public", json={"config": {"invalid": True}})
            ).status_code == 403
    # An identity's display value does not grant administrator authority.
    async with library_api(settings, Identity.user("admin")) as http:
        assert (await http.get("/api/resources/draft")).status_code == 404
        assert (await http.delete("/api/resources/public")).status_code == 403


async def test_resource_usage_guards_and_published_snapshot_outlive_authoring_deletion(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        model = (await http.post("/api/resources", json=model_request("snapshot-private"))).json()
        node = await http.post(
            "/api/resources",
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "name": "Agent",
                "config": {"type": "mock_agent_node", "llm": "$ref:" + model["rid"]},
                "execution": {"profile": "process"},
            },
        )
        assert node.status_code == 201, node.text
        node = node.json()
        assert node["nested_refs"] == [model["rid"]]
        assert (await http.delete("/api/resources/" + model["rid"])).status_code == 409
        created = await http.post(
            "/api/blueprints",
            json={"spec": external_blueprint(node["rid"]).model_dump(mode="json")},
        )
        assert created.status_code == 201, created.text
        blueprint_id = created.json()["blueprint_id"]
        assert (await http.delete("/api/resources/" + node["rid"])).status_code == 409
        imported = await http.put(
            "/api/programs/snapshot/blueprint",
            json={"blueprint_id": blueprint_id, "execution_profile": "thread"},
        )
        assert imported.status_code == 200, imported.text
        assert (
            imported.json()["definition"]["implementation"]["steps"][0]["execution"]["profile"]
            == "process"
        )
        assert all(
            "execution" not in entry
            for entry in imported.json()["definition"]["implementation"]["resources"]
        )
        assert (
            await http.post("/api/programs/snapshot/revisions", json={"expected_version": 1})
        ).status_code == 201
        edited = await http.put(
            "/api/resources/" + node["rid"],
            json={"config": node["cfg_dict"], "execution": {"profile": "thread"}},
        )
        assert edited.status_code == 200, edited.text
        pinned = await http.get("/api/programs/snapshot/revisions/1")
        assert (
            pinned.json()["definition"]["implementation"]["steps"][0]["execution"]["profile"]
            == "process"
        )
        for url in (
            f"/api/blueprints/{blueprint_id}",
            "/api/resources/" + node["rid"],
            "/api/resources/" + model["rid"],
        ):
            removed = await http.delete(url)
            assert removed.status_code == 204, removed.text
        started = await http.post(
            "/api/executions",
            json={
                "execution_id": "after-source-deletion",
                "program": {"program_id": "snapshot", "revision": 1},
                "inputs": GraphState(user_prompt="snapshot input").model_dump(mode="json"),
            },
        )
        assert started.status_code == 202, started.text
        result = await http.get("/api/executions/after-source-deletion/result")
        assert result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["nodes_output"] == {"respond": "Mock echo: snapshot input"}


async def test_resource_cas_fences_legacy_writes_and_versionless_documents(mongo_database):
    repository = MongoResourceAuthoringRepository(
        mongo_database,
        resources="resources",
        descriptors="builtin_resource_descriptors",
        blueprints="blueprints",
    )
    await repository.initialize()
    resource = Resource(
        rid="legacy",
        identity=Identity.user("owner"),
        category="llms",
        type="mock",
        name="Legacy",
        cfg_dict=model_request()["config"],
    )
    document = resource.model_dump(mode="json", exclude={"version", "execution"})
    await mongo_database.resources.insert_one({"_id": resource.rid, **document})
    previous = (await repository.get(resource.rid)).resource
    updated = previous.model_copy(update={"version": 2, "name": "Native"})
    assert previous.version == 1 and await repository.replace(previous, updated)

    def legacy_edit():
        with MongoClient(os.environ["FLAREWARD_TEST_MONGO_URI"]) as client:
            resources = MongoResourceRepository(database=client[mongo_database.name])
            blueprints = MongoBlueprintRepository(database=client[mongo_database.name])
            resources.close()
            blueprints.close()
            registry = ResourcesRegistry(resources, blueprints)
            current = registry.get("legacy")
            current.name = "Legacy edited"
            registry.update(current)

    await asyncio.to_thread(legacy_edit)
    assert not await repository.replace(updated, updated.model_copy(update={"version": 3}))
    assert not await repository.delete(updated)
    current = (await repository.get("legacy")).resource
    assert current.version == 3 and current.name == "Legacy edited"


async def test_resource_http_execution_preference_roundtrip_and_reset(secret_settings):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        rejected = await http.post(
            "/api/resources", json={**model_request(), "execution": {"profile": "process"}}
        )
        assert rejected.status_code == 422, rejected.text
        model = (await http.post("/api/resources", json=model_request())).json()
        created = await http.post(
            "/api/resources",
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "name": "Placed agent",
                "config": {"type": "mock_agent_node", "llm": "$ref:" + model["rid"]},
                "execution": {"profile": "process"},
            },
        )
        assert created.status_code == 201, created.text
        node = created.json()
        url = "/api/resources/" + node["rid"]
        assert (await http.get(url)).json()["execution"] == {"profile": "process"}
        preserved = await http.put(url, json={"config": node["cfg_dict"]})
        assert preserved.status_code == 200, preserved.text
        assert preserved.json()["execution"] == {"profile": "process"}
        stale = await http.put(
            url, json={"config": node["cfg_dict"], "execution": {}, "expected_version": 1}
        )
        assert stale.status_code == 409
        reset = await http.put(
            url, json={"config": node["cfg_dict"], "execution": {}, "expected_version": 2}
        )
        assert reset.status_code == 200, reset.text
        assert reset.json()["execution"] == {"profile": None}


@pytest.mark.parametrize("operation", ["replace", "delete"])
async def test_resource_cas_detects_concurrent_placement_changes(mongo_database, operation):
    repository = MongoResourceAuthoringRepository(
        mongo_database,
        resources="resources",
        descriptors="builtin_resource_descriptors",
        blueprints="blueprints",
    )
    resource = Resource(
        rid="placed-agent",
        identity=Identity.user("owner"),
        category="nodes",
        type="mock_agent_node",
        name="Agent",
        cfg_dict={"type": "mock_agent_node", "llm": "$ref:model"},
    )
    await repository.create(resource)
    previous = (await repository.get(resource.rid)).resource
    # Even a writer that fails to increment the version cannot erase a placement edit.
    await mongo_database.resources.update_one(
        {"_id": resource.rid}, {"$set": {"execution": {"profile": "process"}}}
    )
    applied = (
        await repository.replace(previous, previous.model_copy(update={"version": 2}))
        if operation == "replace"
        else await repository.delete(previous)
    )
    assert not applied
    assert (await repository.get(resource.rid)).resource.execution.profile == "process"


async def test_narrow_blueprint_usage_adapter_preserves_resource_deletion_guards(mongo_database):
    resource = Resource(
        rid="guarded",
        identity=Identity.user("owner"),
        category="tools",
        type="platform_dependency",
        name="Guarded",
        cfg_dict={},
    )
    await mongo_database.resources.insert_one(
        {"_id": resource.rid, **resource.model_dump(mode="json")}
    )
    await mongo_database.blueprints.insert_one(
        {"blueprint_id": "dependent", "rid_refs": [resource.rid]}
    )

    def delete() -> None:
        with MongoClient(os.environ["FLAREWARD_TEST_MONGO_URI"]) as client:
            database = client[mongo_database.name]
            registry = ResourcesRegistry(
                MongoResourceRepository(database=database), MongoBlueprintUsage(database.blueprints)
            )
            registry.delete(resource.rid)

    with pytest.raises(ResourceInUseError) as raised:
        await asyncio.to_thread(delete)
    assert raised.value.by_blueprints == ["dependent"]
    assert await mongo_database.resources.find_one({"_id": resource.rid}) is not None
    await mongo_database.blueprints.delete_one({"blueprint_id": "dependent"})
    await asyncio.to_thread(delete)
    assert await mongo_database.resources.find_one({"_id": resource.rid}) is None
