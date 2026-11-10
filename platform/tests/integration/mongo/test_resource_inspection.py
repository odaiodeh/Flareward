"""Native inspections use actual library dependencies, overlays, credentials, and card builders."""

import hashlib

from support.blueprint_http import library_api
from support.inspection import inspection_elements

from lumora.resources.domain.builtins import BuiltinResourceDescriptor
from lumora.services.identity.domain import Identity


async def test_native_inspection_preserves_dependencies_overlays_and_human_credentials(
    inspection_settings, mongo_database
):
    settings = inspection_settings
    owner = Identity.team("workspace")
    token = "caller-model-private"
    async with library_api(settings, owner, elements=inspection_elements()) as http:
        model = await http.post(
            "/api/resources",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Model",
                "config": {
                    "base_url": "http://unused.invalid",
                    "api_key": token,
                    "expected_digest": hashlib.sha256(token.encode()).hexdigest(),
                },
            },
        )
        assert model.status_code == 201, model.text
        rid = model.json()["rid"]
        node = await http.post(
            "/api/resources",
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "name": "Agent",
                "config": {"llm": "$ref:" + rid},
            },
        )
        assert node.status_code == 201, node.text
        node_id = node.json()["rid"]
        result = await http.post(f"/api/resources/{node_id}/validation", json={})
        assert result.status_code == 200 and result.json()["is_valid"], result.text
        assert result.json()["dependency_results"][rid]["is_valid"]
        editor = await http.post(
            "/api/resources/resource.validate",
            json={"resourceId": node_id, "teamId": owner.id, "userId": "forged-credential-user"},
        )
        assert editor.status_code == 200 and editor.json() == result.json(), editor.text
        assert token not in editor.text
        inline = await http.post(
            "/api/resources/configuration/validation",
            json={"category": "nodes", "type": "mock_agent_node", "config": {"llm": "$ref:" + rid}},
        )
        assert inline.status_code == 200 and inline.json()["is_valid"], inline.text
        descriptor = BuiltinResourceDescriptor(rid=rid, visibility="public")
        await mongo_database.builtin_resource_descriptors.insert_one(
            {"_id": rid, **descriptor.model_dump(mode="json")}
        )
        missing = await http.post(f"/api/resources/{node_id}/validation", json={})
        assert missing.status_code == 200 and not missing.json()["is_valid"], missing.text
        configured = await http.patch(
            f"/api/resources/{rid}/configuration",
            json={"config": {"api_key": token, "label": "Personal"}},
        )
        assert configured.status_code == 200, configured.text
        batch = await http.post(
            "/api/resources/validation", json={"resource_ids": [node_id, "missing", rid]}
        )
        assert batch.status_code == 200, batch.text
        assert [result["element_rid"] for result in batch.json()] == [node_id, "missing", rid]
        assert [result["is_valid"] for result in batch.json()] == [True, False, True]
        cards = await http.post("/api/resources/cards", json={"resource_ids": [node_id]})
        assert cards.status_code == 200 and set(cards.json()) == {node_id, rid}, cards.text
        assert cards.json()[node_id]["capabilities"][0]["description"] == "Personal"
        card = await http.get(f"/api/resources/{node_id}/card")
        assert card.status_code == 200 and card.json() == cards.json()[node_id]
        assert token not in card.text + batch.text + inline.text
        assert (await http.post("/api/resources/cards", json={"resource_ids": []})).json() == {}
        assert (
            await http.post("/api/resources/validation", json={"resource_ids": []})
        ).json() == []
        # Inline dependency validation must use the authenticated caller too.
    async with library_api(
        settings, Identity.user("other"), elements=inspection_elements()
    ) as http:
        assert (await http.get(f"/api/resources/{node_id}/card")).status_code == 404
        denied = await http.post(
            "/api/resources/configuration/validation",
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "config": {"llm": "$ref:" + node_id},
            },
        )
        assert denied.status_code == 404, denied.text


async def test_inspection_rejects_broken_dependencies_cycles_invalid_input_and_provider_failures(
    secret_settings, mongo_database, caplog
):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(
        settings, Identity.team("workspace"), elements=inspection_elements()
    ) as http:
        created = await http.post(
            "/api/resources",
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "name": "Broken",
                "config": {"llm": "$ref:missing"},
            },
        )
        rid = created.json()["rid"]
        broken = await http.post(f"/api/resources/{rid}/validation", json={})
        assert broken.status_code == 200 and not broken.json()["is_valid"], broken.text
        assert (await http.get(f"/api/resources/{rid}/card")).status_code == 404
        await mongo_database.resources.update_one({"_id": rid}, {"$set": {"nested_refs": [rid]}})
        assert (await http.get(f"/api/resources/{rid}/card")).status_code == 422
        invalid = await http.post(
            "/api/resources/configuration/validation",
            json={
                "category": "llms",
                "type": "mock",
                "config": {"api_key": {"invalid": "private-input"}},
            },
        )
        assert invalid.status_code == 422 and "private-input" not in invalid.text
        for body in (
            {"resource_ids": [], "timeout_seconds": 0},
            {"resource_ids": [], "user_id": "forged"},
        ):
            assert (await http.post("/api/resources/validation", json=body)).status_code == 422
        provider = await http.post(
            "/api/resources",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Provider failure",
                "config": {
                    "base_url": "http://unused.invalid",
                    "api_key": "provider-private",
                    "expected_digest": "unused",
                    "fail": True,
                },
            },
        )
        assert provider.status_code == 201, provider.text
        failed = await http.post(f"/api/resources/{provider.json()['rid']}/validation", json={})
        assert failed.status_code == 503, failed.text
        assert "provider-private" not in failed.text + caplog.text
