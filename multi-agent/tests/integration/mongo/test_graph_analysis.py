"""Native graph analysis uses real resolution/storage and retains the YAML response shape."""

import yaml
from mas.core.identity import Identity
from support.blueprint_http import library_api
from support.graph_analysis import graph_blueprint, graph_elements


async def test_graph_analysis_saved_draft_and_legacy_yaml_preserve_reports_without_writes(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    owner = Identity.team("workspace")
    spec = graph_blueprint("graph-private-token")
    async with library_api(settings, owner, elements=graph_elements()) as http:
        names = await http.get("/api/graph/validation/names")
        assert names.status_code == 200 and names.json()["validation_names"] == [
            "dependency",
            "cycle",
            "orphan",
            "channel",
            "required_nodes",
            "orchestrator",
        ]
        assert (await http.get("/api/graph/validation/names.get")).json() == names.json()
        draft = await http.post("/api/blueprints/draft/graph-validation", json={"spec": spec})
        assert draft.status_code == 200 and draft.json()["validation_result"]["is_valid"], (
            draft.text
        )
        assert not await mongo_database.blueprints.count_documents({})
        assert not await mongo_database.program_configuration_secrets.count_documents({})
        legacy = await http.post(
            "/api/graph/validation/all.validate",
            content=yaml.safe_dump(spec),
            headers={"Content-Type": "text/plain"},
        )
        assert legacy.status_code == 200 and legacy.json() == draft.json(), legacy.text
        for path, validator in (
            ("channels", "channel"),
            ("dependencies", "dependency"),
            ("cycles", "cycle"),
            ("orphans", "orphan"),
            ("required_nodes", "required_nodes"),
        ):
            checked = await http.post(
                f"/api/graph/validation/{path}.validate", content=yaml.safe_dump(spec)
            )
            selected = await http.post(
                "/api/blueprints/draft/graph-validation",
                json={"spec": spec, "validator": validator},
            )
            assert checked.status_code == selected.status_code == 200, checked.text + selected.text
            assert checked.json() == selected.json()
            assert checked.json()["validation_result"]["validator_name"] == validator
        created = await http.post("/api/blueprints", json={"spec": spec})
        assert created.status_code == 201, created.text
        blueprint_id = created.json()["blueprint_id"]
        before = await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id})
        secret_count = await mongo_database.program_configuration_secrets.count_documents({})
        saved = await http.post(f"/api/blueprints/{blueprint_id}/graph-validation", json={})
        assert saved.status_code == 200 and saved.json() == draft.json(), saved.text
        assert "graph-private-token" not in saved.text + legacy.text + draft.text
        assert await mongo_database.blueprints.find_one({"blueprint_id": blueprint_id}) == before
        assert (
            await mongo_database.program_configuration_secrets.count_documents({}) == secret_count
        )
        assert not await mongo_database.program_executions.count_documents({})
    async with library_api(settings, Identity.user("foreign"), elements=graph_elements()) as http:
        denied = await http.post(f"/api/blueprints/{blueprint_id}/graph-validation", json={})
        assert denied.status_code == 403, denied.text


async def test_graph_validation_reference_visibility_topology_and_safe_parser_errors(
    secret_settings, mongo_database
):
    settings = secret_settings.model_copy(update={"library": True})
    owner = Identity.user("owner")
    async with library_api(settings, owner, elements=graph_elements()) as http:
        node = await http.post(
            "/api/resources",
            json={
                "category": "nodes",
                "type": "user_question_node",
                "name": "Private input",
                "config": {},
            },
        )
        assert node.status_code == 201, node.text
        spec = graph_blueprint()
        spec["nodes"] = [node for node in spec["nodes"] if node["rid"] != "input"]
        spec["nodes"].append({"rid": "$ref:" + node.json()["rid"]})
        spec["plan"][0]["node"] = "$ref:" + node.json()["rid"]
        resolved = await http.post("/api/blueprints/draft/graph-validation", json={"spec": spec})
        assert resolved.status_code == 200 and resolved.json()["validation_result"]["is_valid"], (
            resolved.text
        )
        broken = graph_blueprint()
        broken["plan"][1]["after"] = "missing-step"
        invalid = await http.post("/api/blueprints/draft/graph-validation", json={"spec": broken})
        assert invalid.status_code == 200 and not invalid.json()["validation_result"]["is_valid"], (
            invalid.text
        )
        dependency = next(
            report
            for report in invalid.json()["validation_result"]["reports"]
            if report["validator_name"] == "dependency"
        )
        assert dependency["messages"][0]["code"] == "MISSING_DEPENDENCY"
        assert invalid.json()["fix_suggestions"]
        for body in (
            {"spec": broken, "validator": "private-unknown"},
            {"spec": {**broken, "retired_field": "private-schema-value"}},
            {"spec": broken, "identity": "forged"},
        ):
            response = await http.post("/api/blueprints/draft/graph-validation", json=body)
            assert response.status_code == 422 and "private-" not in response.text, response.text
        for content in ("[private-parser-value", "- private-parser-value", b"\xff"):
            invalid = await http.post("/api/graph/validation/all.validate", content=content)
            assert invalid.status_code == 422 and "private-parser-value" not in invalid.text
    async with library_api(settings, Identity.team("other"), elements=graph_elements()) as http:
        hidden = await http.post("/api/blueprints/draft/graph-validation", json={"spec": spec})
        assert hidden.status_code == 404 and "Private input" not in hidden.text, hidden.text


async def test_graph_analysis_reports_a_bound_instead_of_enumerating_unbounded_paths(
    secret_settings,
):
    settings = secret_settings.model_copy(update={"library": True})
    spec = graph_blueprint()
    spec["plan"] = [
        {"uid": str(index), "node": "agent", "after": [str(parent) for parent in range(index)]}
        for index in range(14)
    ]
    async with library_api(settings, Identity.user("owner"), elements=graph_elements()) as http:
        result = await http.post("/api/blueprints/draft/graph-validation", json={"spec": spec})
        assert (
            result.status_code == 422
            and result.json()["detail"] == "Graph exceeds the path analysis limit"
        ), result.text
