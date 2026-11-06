"""Stored authoring resources and overlays enter the protected native execution path."""

import asyncio
import json

import pytest
from mas.core.identity import Identity
from mas.domain.programs.models import PathBinding
from mas.graph.state.graph_state import GraphState
from mas.resources.builtin_models import (
    identity_to_key,
)
from outbound.crypto import FieldCipher
from outbound.mongo.configuration_secrets import MongoConfigurationSecrets
from support.blueprint_http import library_api
from support.blueprints import external_blueprint
from support.library_resources import seed_private_agent_resources


async def seed_library(database, owner, cipher):
    agent, _ = await seed_private_agent_resources(database, owner, cipher)
    # Stored legacy metadata is tolerated on reads; new authoring remains strict.
    draft = {**external_blueprint().model_dump(mode="json"), "retired_setting": "legacy"}
    await database.blueprints.insert_one(
        {
            "blueprint_id": "stored-blueprint",
            "identity": owner.model_dump(mode="json"),
            "spec_dict": draft,
            "rid_refs": [agent.rid],
        }
    )


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("team", [False, True])
async def test_stored_blueprint_overlay_is_snapshotted_and_executes_in_native_session(
    secret_settings, mongo_database, profile, team
):
    owner = Identity.team("team") if team else Identity.user("owner")
    cipher = FieldCipher(secret_settings.credential_encryption_key.get_secret_value())
    await seed_library(mongo_database, owner, cipher)
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, owner) as http:
        imported = await http.put(
            "/api/programs/imported/blueprint",
            json={"blueprint_id": "stored-blueprint", "execution_profile": profile},
        )
        assert imported.status_code == 200, imported.text
        assert (
            "caller-private-value" not in imported.text
            and "admin-private-default" not in imported.text
        )
        model = next(
            resource
            for resource in imported.json()["definition"]["implementation"]["resources"]
            if resource["key"]["rid"] == "library-model"
        )
        store = MongoConfigurationSecrets(mongo_database, cipher)
        value = await store.get(owner, model["config"]["api_key"])
        assert value.get_secret_value() == "caller-private-value"
        revision = await http.post("/api/programs/imported/revisions", json={"expected_version": 1})
        assert revision.status_code == 201, revision.text
        # Edits to library resources/overlays do not rewrite an existing revision.
        await mongo_database.builtin_user_configs.update_one(
            {"identity_key": identity_to_key(owner)},
            {"$set": {"fields.api_key": cipher.encrypt("changed-private-value")}},
        )
        bindings = {
            name: PathBinding(path=(name,)).model_dump(mode="json")
            for name in GraphState.model_fields
        }
        session = await http.post(
            "/api/sessions",
            json={
                "program": {"program_id": "imported", "revision": 1},
                "blueprint_id": "stored-blueprint",
                "input_bindings": bindings,
                "output_bindings": bindings,
            },
        )
        assert session.status_code == 201, session.text
        run_id = session.json()["run_id"]
        started = await http.post(
            f"/api/sessions/{run_id}/executions",
            json={"execution_id": "stored-turn", "inputs": {"user_prompt": "stored input"}},
        )
        assert started.status_code == 202, started.text
        async with asyncio.timeout(15):
            result = await http.get("/api/executions/stored-turn/result")
        assert result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["nodes_output"] == {"respond": "Mock echo: stored input"}
        assert result.json()["context"]["tags"]["credential_user_id"] == "human"
        assert (
            await store.get(owner, model["config"]["api_key"])
        ).get_secret_value() == "caller-private-value"
        documents = await mongo_database.program_executions.find().to_list()
        encoded = json.dumps(documents, default=str)
        for private in ("caller-private-value", "admin-private-default", "changed-private-value"):
            assert private not in encoded


@pytest.mark.parametrize("hidden", ["blueprint", "resource", "draft_builtin", "missing_dependency"])
async def test_import_rejects_inaccessible_authoring_data_before_program_save(
    secret_settings, mongo_database, hidden
):
    owner = Identity.user("owner")
    cipher = FieldCipher(secret_settings.credential_encryption_key.get_secret_value())
    await seed_library(mongo_database, owner, cipher)
    if hidden == "blueprint":
        await mongo_database.blueprints.update_one({}, {"$set": {"identity.id": "other"}})
    elif hidden == "resource":
        await mongo_database.resources.update_one(
            {"_id": "library-agent"}, {"$set": {"identity.id": "other"}}
        )
    elif hidden == "draft_builtin":
        await mongo_database.builtin_resource_descriptors.update_one(
            {}, {"$set": {"visibility": "draft"}}
        )
    else:
        await mongo_database.resources.delete_one({"_id": "library-model"})
    async with library_api(secret_settings.model_copy(update={"library": True}), owner) as http:
        imported = await http.put(
            "/api/programs/imported/blueprint", json={"blueprint_id": "stored-blueprint"}
        )
        assert imported.status_code == (403 if hidden == "blueprint" else 404), imported.text
        assert not await mongo_database.program_drafts.count_documents({})
