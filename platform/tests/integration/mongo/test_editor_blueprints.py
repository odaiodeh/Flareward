"""Existing editor paths use native authoring policy and safe resolved display snapshots."""

import json

import pytest
import yaml
from support.blueprint_http import library_api
from support.blueprints import external_blueprint, inline_blueprint

from flareward.services.identity.domain import Identity


@pytest.mark.parametrize("team", [False, True])
async def test_editor_blueprints_preserve_sources_shortcuts_versions_and_display(
    secret_settings, mongo_database, team
):
    owner = Identity.team("workspace") if team else Identity.user("owner")
    settings = secret_settings.model_copy(update={"library": True})
    spec = inline_blueprint("editor-private-value").model_dump(mode="json")
    async with library_api(settings, owner) as http:
        created = await http.post(
            "/api/blueprints/blueprint.save",
            json={"blueprintRaw": yaml.safe_dump(spec), "metadata": {"keep": True}},
        )
        assert created.status_code == 201, created.text
        blueprint_id = created.json()["blueprint_id"]
        params = {"blueprintId": blueprint_id}
        info = await http.get("/api/blueprints/blueprint.info.get", params=params)
        assert info.status_code == 200 and info.json()["user_id"] == owner.id, info.text
        assert "editor-private-value" not in info.text
        assert info.json()["spec_dict"]["llms"][0]["config"]["api_key"].startswith(
            "flareward-secret:"
        )
        summary = await http.get("/api/blueprints/available.blueprints.summary.get")
        assert summary.json()[0]["name"] == spec["name"], summary.text
        assert "spec_dict" not in summary.text and summary.json()[0]["user_id"] == owner.id
        assert (await http.get("/api/blueprints/available.blueprints.get")).json()[0][
            "blueprint_id"
        ] == blueprint_id
        shortcut = await http.put(
            "/api/blueprints/blueprint.prompt-shortcuts.set",
            json={"blueprintId": blueprint_id, "prompts": [{"text": "Run"}]},
        )
        assert shortcut.status_code == 200, shortcut.text
        prompt = shortcut.json()
        assert (
            await http.get("/api/blueprints/blueprint.prompt-shortcuts.get", params=params)
        ).json() == prompt
        before = await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id})
        secret_count = await mongo_database.program_configuration_secrets.count_documents({})
        resolved = await http.get(
            "/api/blueprints/available.blueprints.resolved.get", params=params
        )
        assert resolved.status_code == 200, resolved.text
        assert resolved.json()["spec_dict"]["llms"][0]["config"]["api_key"] == "********"
        assert resolved.json()["spec_dict"]["prompt_shortcuts"] == prompt["prompts"]
        assert resolved.json()["missing_resources"] == {}
        page = await http.get("/api/blueprints/available.blueprints.resolved.get?limit=1")
        assert page.json()["items"] == [resolved.json()], page.text
        assert page.json()["total"] == 1
        assert await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id}) == before
        assert (
            await mongo_database.program_configuration_secrets.count_documents({}) == secret_count
        )
        updated_spec = {**info.json()["spec_dict"], "name": "Edited source"}
        updated_spec.pop("prompt_shortcuts", None)
        edited = await http.put(
            "/api/blueprints/blueprint.update",
            json={
                "blueprintId": blueprint_id,
                "blueprintRaw": json.dumps(updated_spec),
                "expected_version": 2,
            },
        )
        assert edited.status_code == 200 and edited.json()["version"] == 3, edited.text
        conflict = await http.put(
            "/api/blueprints/blueprint.update",
            json={
                "blueprintId": blueprint_id,
                "blueprintRaw": json.dumps(updated_spec),
                "expected_version": 2,
            },
        )
        assert conflict.status_code == 409, conflict.text
        assert (
            await http.put(
                "/api/blueprints/blueprint.metadata.set",
                json={"blueprintId": blueprint_id, "metadata": {"usageScope": "public"}},
            )
        ).status_code == 200
        current = (await http.get("/api/blueprints/blueprint.info.get", params=params)).json()
        assert current["metadata"] == {"keep": True, "usageScope": "public"}
        assert current["spec_dict"]["prompt_shortcuts"] == prompt["prompts"]
        assert (await http.delete("/api/blueprints/remove.blueprint", params=params)).json() == {
            "status": "success"
        }
        assert (
            await http.get("/api/blueprints/blueprint.info.get", params=params)
        ).status_code == 404


async def test_editor_blueprint_sources_errors_and_foreign_ownership_are_safe(secret_settings):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        for source in (
            "[private-invalid-source",
            "null",
            "[]",
            '{"plan":[],"unknown":"private-invalid-source"}',
        ):
            invalid = await http.post(
                "/api/blueprints/blueprint.save", json={"blueprintRaw": source}
            )
            assert invalid.status_code == 422 and "private-invalid-source" not in invalid.text
        spoofed = await http.post(
            "/api/blueprints/blueprint.save",
            json={
                "blueprintRaw": json.dumps(inline_blueprint().model_dump(mode="json")),
                "userId": "another-owner",
            },
        )
        assert spoofed.status_code == 422 and "another-owner" not in spoofed.text
        created = await http.post(
            "/api/blueprints/blueprint.save",
            json={"blueprintRaw": json.dumps(external_blueprint("gone").model_dump(mode="json"))},
        )
        assert created.status_code == 201, created.text
        blueprint_id = created.json()["blueprint_id"]
        params = {"blueprintId": blueprint_id}
        missing = await http.get("/api/blueprints/available.blueprints.resolved.get", params=params)
        assert missing.status_code == 200 and "gone" in missing.json()["missing_resources"], (
            missing.text
        )
        assert missing.json()["spec_dict"]["nodes"] == []
    async with library_api(settings, Identity.user("other")) as http:
        assert (await http.get("/api/blueprints/available.blueprints.get")).json() == []
        for path in (
            "blueprint.info.get",
            "available.blueprints.resolved.get",
            "blueprint.prompt-shortcuts.get",
        ):
            assert (await http.get(f"/api/blueprints/{path}", params=params)).status_code == 403
        assert (
            await http.delete("/api/blueprints/remove.blueprint", params=params)
        ).status_code == 403
        update = await http.put(
            "/api/blueprints/blueprint.update",
            json={"blueprintId": blueprint_id, "blueprintRaw": "[private-invalid-source"},
        )
        assert update.status_code == 403, update.text
        metadata = await http.put(
            "/api/blueprints/blueprint.metadata.set",
            json={"blueprintId": blueprint_id, "metadata": {"usageScope": "public"}},
        )
        assert metadata.status_code == 403, metadata.text
