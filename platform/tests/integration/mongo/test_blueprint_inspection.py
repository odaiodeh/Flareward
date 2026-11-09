"""Saved/draft inspection hydrates private references locally and preserves library policy."""

from support.blueprint_http import library_api
from support.blueprints import external_blueprint, inline_blueprint
from support.inspection import inspection_elements

from flareward.resources.domain.builtins import BuiltinResourceDescriptor
from flareward.services.identity.domain import Identity


async def test_draft_and_saved_blueprint_probes_hydrate_credentials_without_mutating_authoring(
    inspection_settings, mongo_database
):
    owner = Identity.team("workspace")
    spec = inline_blueprint("caller-model-private").model_dump(mode="json")
    async with library_api(inspection_settings, owner, elements=inspection_elements()) as http:
        validated = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert validated.status_code == 200 and validated.json()["is_valid"], validated.text
        assert validated.json()["element_results"]["agent"]["dependency_results"]["model"][
            "is_valid"
        ]
        cards = await http.post("/api/blueprints/draft/cards", json={"spec": spec})
        assert cards.status_code == 200 and set(cards.json()) == {"model", "agent"}, cards.text
        assert not await mongo_database.blueprints.count_documents({})
        assert not await mongo_database.program_configuration_secrets.count_documents({})
        created = await http.post("/api/blueprints", json={"spec": spec})
        assert created.status_code == 201, created.text
        blueprint_id = created.json()["blueprint_id"]
        protected_spec = created.json()["spec_dict"]
        before = await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id})
        count = await mongo_database.program_configuration_secrets.count_documents({})
        saved = await http.post(f"/api/blueprints/{blueprint_id}/validation", json={})
        assert saved.status_code == 200 and saved.json()["is_valid"], saved.text
        saved_cards = await http.get(f"/api/blueprints/{blueprint_id}/cards")
        assert saved_cards.status_code == 200 and saved_cards.json() == cards.json(), (
            saved_cards.text
        )
        assert "caller-model-private" not in saved.text + saved_cards.text + created.text
        assert await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id}) == before
        assert await mongo_database.program_configuration_secrets.count_documents({}) == count
        await mongo_database.blueprints.update_one(
            {"blueprint_id": blueprint_id}, {"$set": {"spec_dict.retired_field": "legacy"}}
        )
        legacy = await http.post(f"/api/blueprints/{blueprint_id}/validation", json={})
        assert legacy.status_code == 200 and legacy.json()["is_valid"], legacy.text
        invalid = await http.post(
            "/api/blueprints/draft/validation",
            json={"spec": {**spec, "retired_field": "invalid-private"}},
        )
        assert invalid.status_code == 422 and "invalid-private" not in invalid.text
    async with library_api(
        inspection_settings, Identity.user("other"), elements=inspection_elements()
    ) as http:
        assert (await http.get(f"/api/blueprints/{blueprint_id}/cards")).status_code == 403
        assert (
            await http.post(f"/api/blueprints/{blueprint_id}/validation", json={})
        ).status_code == 403
        rejected = await http.post("/api/blueprints/draft/cards", json={"spec": protected_spec})
        assert rejected.status_code == 403, rejected.text


async def test_referenced_blueprint_inspection_applies_overlays_and_reports_hidden_dependencies(
    inspection_settings, mongo_database, caplog
):
    owner = Identity.team("workspace")
    async with library_api(inspection_settings, owner, elements=inspection_elements()) as http:
        model = await http.post(
            "/api/resources",
            json={
                "category": "llms",
                "type": "mock",
                "name": "Model",
                "config": {"base_url": "http://unused.invalid", "api_key": "admin-private"},
            },
        )
        assert model.status_code == 201, model.text
        model_id = model.json()["rid"]
        descriptor = BuiltinResourceDescriptor(rid=model_id, visibility="public")
        await mongo_database.builtin_resource_descriptors.insert_one(
            {"_id": model_id, **descriptor.model_dump(mode="json")}
        )
        node = await http.post(
            "/api/resources",
            json={
                "category": "nodes",
                "type": "mock_agent_node",
                "name": "Agent",
                "config": {"llm": "$ref:" + model_id},
            },
        )
        assert node.status_code == 201, node.text
        spec = external_blueprint(node.json()["rid"]).model_dump(mode="json")
        missing = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert missing.status_code == 200 and not missing.json()["is_valid"], missing.text
        assert (
            await http.patch(
                f"/api/resources/{model_id}/configuration",
                json={"config": {"api_key": "caller-model-private", "label": "Personal"}},
            )
        ).status_code == 200
        validated = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert validated.status_code == 200 and validated.json()["is_valid"], validated.text
        cards = await http.post("/api/blueprints/draft/cards", json={"spec": spec})
        assert cards.status_code == 200, cards.text
        assert cards.json()[node.json()["rid"]]["capabilities"][0]["description"] == "Personal"
        await mongo_database.resources.update_one(
            {"_id": model_id}, {"$set": {"cfg_dict.fail": True}}
        )
        failed = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert failed.status_code == 503, failed.text
        assert "caller-model-private" not in failed.text + caplog.text
        await mongo_database.resources.update_one(
            {"_id": model_id}, {"$set": {"cfg_dict.fail": False, "cfg_dict.report_failure": True}}
        )
        reported = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert reported.status_code == 200 and not reported.json()["is_valid"], reported.text
        assert "[redacted]" in reported.text and "caller-model-private" not in reported.text
        await mongo_database.builtin_resource_descriptors.update_one(
            {"_id": model_id}, {"$set": {"visibility": "draft"}}
        )
        hidden = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert hidden.status_code == 200 and not hidden.json()["is_valid"], hidden.text
        assert not hidden.json()["element_results"][model_id]["is_valid"]
        assert (
            await http.post("/api/blueprints/draft/cards", json={"spec": spec})
        ).status_code == 404


async def test_blueprint_inspection_rejects_missing_local_and_wrong_category_before_probes(
    secret_settings,
):
    async with library_api(
        secret_settings.model_copy(update={"library": True}), Identity.user("owner")
    ) as http:
        spec = inline_blueprint().model_dump(mode="json")
        spec["llms"] = []
        missing = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert missing.status_code == 200 and not missing.json()["is_valid"], missing.text
        assert (
            await http.post("/api/blueprints/draft/cards", json={"spec": spec})
        ).status_code == 404
        spec["nodes"][0]["config"]["llm"] = "agent"
        cycle = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert cycle.status_code == 422, cycle.text
        spec["nodes"].append(
            {
                "rid": "other",
                "name": "Other agent",
                "type": "mock_agent_node",
                "config": {"type": "mock_agent_node", "llm": None},
            }
        )
        spec["nodes"][0]["config"]["llm"] = "other"
        mismatch = await http.post("/api/blueprints/draft/validation", json={"spec": spec})
        assert mismatch.status_code == 200 and not mismatch.json()["is_valid"], mismatch.text
        assert (
            "category mismatch"
            in mismatch.json()["element_results"]["agent"]["messages"][0]["message"]
        )
        assert (
            await http.post("/api/blueprints/draft/cards", json={"spec": spec})
        ).status_code == 422
        for body in (
            {"spec": {}},
            {"spec": {}, "user_id": "forged"},
            {"spec": {}, "timeout_seconds": 0},
        ):
            assert (
                await http.post("/api/blueprints/draft/validation", json=body)
            ).status_code == 422
