"""Native authoring and legacy storage share atomic edit semantics and protected values."""

import asyncio
import os

from mas.blueprints.models.blueprint import BlueprintDraft
from mas.blueprints.models.prompt_shortcuts import PromptShortcuts
from mas.core.identity import Identity
from outbound.mongo.blueprint_authoring_repository import MongoBlueprintAuthoringRepository
from outbound.mongo.blueprint_repository import MongoBlueprintRepository
from pymongo import MongoClient
from support.blueprint_http import library_api
from support.blueprints import inline_blueprint


async def test_http_authoring_preserves_editing_semantics_and_protects_configuration(
    secret_settings, mongo_database
):
    owner = Identity.user("owner")
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, owner) as http:
        spec = inline_blueprint("private-authoring-value").model_dump(mode="json")
        created = await http.post(
            "/api/blueprints", json={"spec": spec, "metadata": {"keep": True}}
        )
        assert created.status_code == 201, created.text
        assert "private-authoring-value" not in created.text
        document = created.json()
        blueprint_id = document["blueprint_id"]
        assert document["version"] == 1
        assert (await http.post("/api/blueprints", json={"spec": spec})).status_code == 409
        shortcuts = await http.put(
            f"/api/blueprints/{blueprint_id}/prompt-shortcuts", json={"prompts": [{"text": "Run"}]}
        )
        assert shortcuts.status_code == 200, shortcuts.text
        prompt = shortcuts.json()["spec_dict"]["prompt_shortcuts"]
        edited = {**document["spec_dict"], "name": "Edited"}
        edited.pop("prompt_shortcuts", None)
        updated = await http.put(
            f"/api/blueprints/{blueprint_id}", json={"spec": edited, "expected_version": 2}
        )
        assert updated.status_code == 200, updated.text
        assert updated.json()["spec_dict"]["prompt_shortcuts"] == prompt
        metadata = await http.patch(
            f"/api/blueprints/{blueprint_id}/metadata",
            json={"metadata": {"added": "value"}, "expected_version": 3},
        )
        assert metadata.json()["metadata"] == {"keep": True, "added": "value"}, metadata.text
        listed = await http.get("/api/blueprints?limit=1")
        assert listed.json()["total"] == len(listed.json()["items"]) == 1
        saved = await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id})
        assert "private-authoring-value" not in str(saved)
        imported = await http.put(
            "/api/programs/authored/blueprint", json={"blueprint_id": blueprint_id}
        )
        assert imported.status_code == 200, imported.text
        published = await http.post(
            "/api/programs/authored/revisions", json={"expected_version": 1}
        )
        assert published.status_code == 201, published.text
        removed = await http.delete(f"/api/blueprints/{blueprint_id}?expected_version=4")
        assert removed.status_code == 204, removed.text
        assert (await http.get(f"/api/blueprints/{blueprint_id}")).status_code == 404
        assert (await http.get("/api/programs/authored/revisions/1")).status_code == 200


async def test_http_authoring_ownership_conflicts_and_safe_validation(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        created = await http.post(
            "/api/blueprints", json={"spec": inline_blueprint().model_dump(mode="json")}
        )
        blueprint_id = created.json()["blueprint_id"]
        changes = await asyncio.gather(
            *[
                http.patch(
                    f"/api/blueprints/{blueprint_id}/metadata",
                    json={"metadata": {"winner": number}, "expected_version": 1},
                )
                for number in range(5)
            ]
        )
        assert [response.status_code for response in changes].count(200) == 1
        assert [response.status_code for response in changes].count(409) == 4
        invalid = await http.post(
            "/api/blueprints",
            json={
                "spec": {
                    "plan": [],
                    "llms": [{"type": "unknown", "config": {"api_key": "private-invalid-value"}}],
                }
            },
        )
        assert invalid.status_code == 422 and "private-invalid-value" not in invalid.text
        malformed = await http.post("/api/blueprints", json={"spec": "private-invalid-value"})
        assert malformed.status_code == 422 and "private-invalid-value" not in malformed.text
    async with library_api(settings, Identity.user("other")) as http:
        assert (await http.get("/api/blueprints")).json()["total"] == 0
        assert (await http.get(f"/api/blueprints/{blueprint_id}")).status_code == 403
        assert (await http.delete(f"/api/blueprints/{blueprint_id}")).status_code == 403
        assert (
            await http.patch(
                f"/api/blueprints/{blueprint_id}/metadata", json={"metadata": {"bad": True}}
            )
        ).status_code == 403


async def test_native_cas_fences_legacy_edits_and_updates_versionless_documents(mongo_database):
    owner = Identity.user("owner")
    repository = MongoBlueprintAuthoringRepository(mongo_database.blueprints)
    await repository.initialize()
    await mongo_database.blueprints.insert_one(
        {
            "blueprint_id": "legacy",
            "identity": owner.model_dump(mode="json"),
            "spec_dict": {"name": "Legacy", "plan": []},
        }
    )
    original = await repository.get("legacy")
    assert original.version == 0
    updated = original.model_copy(update={"version": 1, "metadata": {"native": True}})
    assert await repository.replace(original, updated)

    def legacy_edit():
        with MongoClient(os.environ["UNIFAI_TEST_MONGO_URI"]) as client:
            legacy = MongoBlueprintRepository(database=client[mongo_database.name])
            legacy.close()  # Borrowed repositories do not close the client's owned scope.
            legacy.update(
                blueprint_id="legacy",
                spec=BlueprintDraft(name="Legacy edited", plan=[]),
                rid_refs=[],
            )
            legacy.set_metadata(blueprint_id="legacy", metadata={"legacy": True})
            legacy.set_prompt_shortcuts(
                blueprint_id="legacy", shortcuts=PromptShortcuts.parse([{"text": "Run"}])
            )

    await asyncio.to_thread(legacy_edit)
    assert not await repository.replace(updated, updated.model_copy(update={"version": 2}))
    assert not await repository.delete(updated)
    current = await repository.get("legacy")
    assert current.version == 4 and current.metadata == {"native": True, "legacy": True}
