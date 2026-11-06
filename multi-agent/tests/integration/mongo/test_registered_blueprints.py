"""Plugins use the same HTTP authoring, inspection, publication, and engine path."""

import hashlib

import pytest
from jsonschema import Draft202012Validator
from mas.core.identity import Identity
from mas.graph.state.graph_state import GraphState
from support.blueprint_http import library_api
from support.blueprints import dependency_blueprint
from support.elements import element_registry


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("saved_resources", [False, True])
async def test_registered_blueprint_runs_transitive_dependencies_from_inline_or_saved_resources(
    secret_settings, mongo_database, profile, saved_resources
):
    settings = secret_settings.model_copy(update={"library": True})
    spec = dependency_blueprint(profile)
    async with library_api(settings, Identity.user("owner"), elements=element_registry()) as http:
        schema = await http.get("/api/blueprints/schema")
        assert schema.status_code == 200, schema.text
        Draft202012Validator(schema.json()).validate(spec)
        if saved_resources:
            identities = {}
            for category in ("tools", "nodes"):
                for resource in spec[category]:
                    config = dict(resource["config"])
                    if "dependency" in config:
                        config["dependency"] = "$ref:" + identities[config["dependency"]]
                    created = await http.post(
                        "/api/resources",
                        json={
                            "category": category,
                            "type": resource["type"],
                            "name": resource["name"],
                            "config": config,
                            "execution": resource.get("execution", {}),
                        },
                    )
                    assert created.status_code == 201, created.text
                    identities[resource["rid"]] = created.json()["rid"]
            spec["tools"] = []
            spec["nodes"] = [{"rid": "$ref:" + identities["echo"]}]
            spec["plan"][0]["node"] = "$ref:" + identities["echo"]
        authored = await http.post("/api/blueprints", json={"spec": spec})
        assert authored.status_code == 201, authored.text
        blueprint_id = authored.json()["blueprint_id"]
        cards = await http.get(f"/api/blueprints/{blueprint_id}/cards")
        assert cards.status_code == 200 and len(cards.json()) == 3, cards.text
        validated = await http.post(f"/api/blueprints/{blueprint_id}/validation", json={})
        assert validated.status_code == 200 and validated.json()["is_valid"], validated.text
        imported = await http.put(
            "/api/programs/plugin/blueprint", json={"blueprint_id": blueprint_id}
        )
        assert imported.status_code == 200, imported.text
        resources = imported.json()["definition"]["implementation"]["resources"]
        assert len(resources) == 3
        assert (
            imported.json()["definition"]["implementation"]["steps"][0]["execution"]["profile"]
            == profile
        )
        assert (
            await http.post("/api/programs/plugin/revisions", json={"expected_version": 1})
        ).status_code == 201
        started = await http.post(
            "/api/executions",
            json={
                "execution_id": "plugin-run",
                "program": {"program_id": "plugin", "revision": 1},
                "inputs": GraphState(user_prompt="input").model_dump(mode="json"),
            },
        )
        assert started.status_code == 202, started.text
        result = await http.get("/api/executions/plugin-run/result")
        assert result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["output"] == "plugin:middle:input"


async def test_registered_blueprint_protects_plugin_secret_hints_before_persistence(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    secret = "private-plugin-value"
    spec = {
        "name": "Private plugin blueprint",
        "tools": [
            {
                "rid": "private",
                "name": "Private tool",
                "type": "platform_secret_tool",
                "config": {"api_key": secret},
            }
        ],
        "nodes": [
            {
                "rid": "node",
                "name": "Secret consumer",
                "type": "platform_secret_node",
                "config": {"tool": "private"},
            }
        ],
        "plan": [{"uid": "consume", "node": "node"}],
    }
    async with library_api(settings, Identity.user("owner"), elements=element_registry()) as http:
        created = await http.post("/api/blueprints", json={"spec": spec})
        assert created.status_code == 201 and secret not in created.text, created.text
        document = await mongo_database.blueprints.find_one({})
        assert secret not in str(document)
        imported = await http.put(
            "/api/programs/private-plugin/blueprint",
            json={"blueprint_id": created.json()["blueprint_id"]},
        )
        assert imported.status_code == 200 and secret not in imported.text, imported.text
        assert (
            await http.post("/api/programs/private-plugin/revisions", json={"expected_version": 1})
        ).status_code == 201
        started = await http.post(
            "/api/executions",
            json={
                "execution_id": "private-plugin-run",
                "program": {"program_id": "private-plugin", "revision": 1},
                "inputs": GraphState().model_dump(mode="json"),
            },
        )
        assert started.status_code == 202, started.text
        result = await http.get("/api/executions/private-plugin-run/result")
        assert result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["output"] == hashlib.sha256(secret.encode()).hexdigest()
        assert secret not in result.text
