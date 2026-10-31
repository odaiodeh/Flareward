"""Existing UI requests reach native services, encryption and ownership through FastAPI."""

from mas.core.identity import Identity
from mas.elements.nodes.codex_agent.spec.spec import CodexAgentNodeElementSpec
from support.blueprint_http import library_api
from support.blueprints import library_elements


async def test_editor_catalog_uses_installed_specs_and_preserves_dynamic_forms(secret_settings):
    elements = library_elements()
    elements.register_spec_class(CodexAgentNodeElementSpec)
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner"), elements=elements) as http:
        legacy = await http.get("/api/catalog/elements.list.get")
        native = await http.get("/api/catalog/elements")
        assert legacy.status_code == 200 and legacy.json() == native.json()
        assert "sandboxes" not in legacy.json()["elements"]
        codex = next(
            item
            for item in legacy.json()["elements"]["nodes"]
            if item["type"] == "codex_agent_node"
        )
        assert codex["name"] == "Codex Agent Node"
        detail = await http.get(
            "/api/catalog/element.spec.get", params={"category": "nodes", "type": codex["type"]}
        )
        assert detail.status_code == 200, detail.text
        assert detail.json()["config_schema"]["properties"]["model"]
        assert "model" in detail.json()["config_schema"]["required"]
        same = await http.get("/api/catalog/elements/nodes/codex_agent_node")
        assert same.json() == detail.json()
        assert (await http.get("/api/catalog/elements/nodes/missing")).status_code == 404
        assert (
            await http.get(
                "/api/catalog/element.spec.get", params={"category": "invalid", "type": "bad"}
            )
        ).status_code == 422
        categories = await http.get("/api/catalog/categories.list.get")
        assert categories.json() == (await http.get("/api/catalog/categories")).json()


async def test_editor_resource_crud_uses_native_persistence_and_conflict_checks(secret_settings):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        schema = await http.get("/api/resources/resource.schema")
        assert schema.status_code == 200 and "name" in schema.json()["properties"]
        assert "hidden" in schema.json()["properties"]["identity"]["hints"]
        created = await http.post(
            "/api/resources/resource.save",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Editor model",
                "config": {"base_url": "http://unused.invalid", "api_key": "editor-private-value"},
            },
        )
        assert created.status_code == 201, created.text
        assert "editor-private-value" not in created.text
        saved = created.json()
        rid = saved["rid"]
        listed = await http.get(
            "/api/resources/resources.list", params={"category": "llms", "limit": 1}
        )
        assert listed.status_code == 200, listed.text
        assert listed.json()["resources"] == [saved]
        assert listed.json()["pagination"] == {
            "total": 1,
            "offset": 0,
            "limit": 1,
            "has_more": False,
        }
        assert (
            await http.get("/api/resources/resource.get", params={"resourceId": rid})
        ).json() == saved
        assert (await http.get("/api/resources/" + rid)).json() == saved
        changed = await http.put(
            "/api/resources/resource.update",
            json={
                "resourceId": rid,
                "name": "Edited",
                "config": saved["cfg_dict"],
                "expected_version": 1,
            },
        )
        assert changed.status_code == 200 and changed.json()["version"] == 2, changed.text
        conflict = await http.put(
            "/api/resources/resource.update",
            json={
                "resourceId": rid,
                "name": "Stale",
                "config": saved["cfg_dict"],
                "expected_version": 1,
            },
        )
        assert conflict.status_code == 409
        assert (
            await http.delete(
                "/api/resources/resource.delete", params={"resourceId": rid, "expected_version": 2}
            )
        ).status_code == 204
        assert (await http.get("/api/resources/" + rid)).status_code == 404


async def test_editor_resource_endpoints_do_not_trust_authored_owner(secret_settings):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        created = await http.post(
            "/api/resources/resource.save",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Private model",
                "config": {"base_url": "http://unused.invalid", "api_key": "EMPTY"},
            },
        )
        assert created.status_code == 201, created.text
        saved = created.json()
    async with library_api(settings, Identity.user("other")) as http:
        assert (
            await http.get("/api/resources/resource.get", params={"resourceId": saved["rid"]})
        ).status_code == 404
        write = await http.put(
            "/api/resources/resource.update",
            json={
                "resourceId": saved["rid"],
                "config": saved["cfg_dict"],
                "name": "Stolen",
            },
        )
        assert write.status_code == 403
        assert (
            await http.delete("/api/resources/resource.delete", params={"resourceId": saved["rid"]})
        ).status_code == 403
        spoof = await http.post(
            "/api/resources/resource.save",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Spoof",
                "identity": {"type": "user", "id": "owner"},
                "config": {},
            },
        )
        assert spoof.status_code == 422
