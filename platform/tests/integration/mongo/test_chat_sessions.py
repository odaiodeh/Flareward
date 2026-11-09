"""Existing UI session routes run protected snapshots without a session wrapper engine run."""

import json

import pytest
from support.blueprint_http import library_api
from support.blueprints import inline_blueprint

from flareward.services.identity.domain import Identity


@pytest.mark.parametrize(
    "selection,expected", [(None, "thread"), ({}, None), ({"profile": "thread"}, "thread")]
)
async def test_chat_snapshot_pins_workflow_defaults_and_step_overrides(
    secret_settings, selection, expected
):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        spec = inline_blueprint().model_dump(mode="json")
        spec["execution_profile"] = "process"
        spec["nodes"][0]["execution"] = {"profile": "thread"}
        spec["plan"][0]["execution"] = selection
        blueprint = await http.post("/api/blueprints", json={"spec": spec})
        assert blueprint.status_code == 201, blueprint.text
        blueprint_id = blueprint.json()["blueprint_id"]
        session = await http.post(
            "/api/sessions/user.session.create", json={"blueprintId": blueprint_id}
        )
        assert session.status_code == 200, session.text
        session_id = session.json()
        reference = (await http.get(f"/api/sessions/{session_id}")).json()["program"]
        url = f"/api/programs/{reference['program_id']}/revisions/{reference['revision']}"
        definition = (await http.get(url)).json()["definition"]
        assert definition["execution_profile"] == "process"
        assert definition["implementation"]["steps"][0]["execution"]["profile"] == expected
        # Subsequent authoring changes cannot rewrite the existing session's publication.
        spec["execution_profile"] = "thread"
        assert (
            await http.put(f"/api/blueprints/{blueprint_id}", json={"spec": spec})
        ).status_code == 200
        for execution_id in ("placed-one", "placed-two"):
            response = await http.post(
                "/api/sessions/user.session.submit",
                json={
                    "sessionId": session_id,
                    "executionId": execution_id,
                    "inputs": {"user_prompt": "Placement"},
                },
            )
            assert response.status_code == 202, response.text
            result = await http.get(f"/api/executions/{execution_id}/result")
            assert result.json()["phase"] == "completed", result.text
            assert result.json()["result"]["nodes_output"]["respond"] == "Mock echo: Placement"
        assert (await http.get(url)).json()["definition"] == definition


@pytest.mark.parametrize(
    "placement",
    [
        {"execution": {"environment": "missing"}},
        {"execution": {"profile": "thread", "environment": "workspace"}},
        {"condition_execution": {"profile": "thread"}},
    ],
)
async def test_invalid_step_placement_is_rejected_during_authoring(secret_settings, placement):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        spec = inline_blueprint().model_dump(mode="json")
        spec["plan"][0].update(placement)
        rejected = await http.post("/api/blueprints", json={"spec": spec})
        assert rejected.status_code == 422, rejected.text


@pytest.mark.parametrize("team", [False, True])
async def test_chat_sessions_pin_blueprints_and_preserve_multiple_turns(secret_settings, team):
    owner = Identity.team("workspace") if team else Identity.user("owner")
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, owner) as http:
        spec = inline_blueprint("chat-private-value").model_dump(mode="json")
        blueprint = await http.post("/api/blueprints", json={"spec": spec})
        blueprint_id = blueprint.json()["blueprint_id"]
        created = await http.post(
            "/api/sessions/user.session.create",
            json={
                "blueprintId": blueprint_id,
                "hitlEnabled": True,
                "metadata": {"title": "Pinned chat"},
            },
        )
        assert created.status_code == 200 and isinstance(created.json(), str), created.text
        session_id = created.json()
        params = {"sessionId": session_id}
        saved = (await http.get(f"/api/sessions/{session_id}")).json()
        assert saved["metadata"]["hitl_enabled"] is True and saved["status"] == "PENDING"
        reference = saved["program"]
        assert reference["revision"] == 1
        revision = await http.get(f"/api/programs/{reference['program_id']}/revisions/1")
        assert "chat-private-value" not in revision.text
        # A later blueprint edit must affect new sessions while this one retains its snapshot.
        changed = {**blueprint.json()["spec_dict"]}
        changed["nodes"][0]["config"]["echo_message"] = "New snapshot"
        assert (
            await http.put(f"/api/blueprints/{blueprint_id}", json={"spec": changed})
        ).status_code == 200
        later = await http.post(
            "/api/sessions/user.session.create", json={"blueprintId": blueprint_id}
        )
        assert later.status_code == 200, later.text
        later_id = later.json()
        assert (await http.get(f"/api/sessions/{later_id}")).json()["program"] != reference
        for execution_id, prompt in (("chat-one", "First"), ("chat-two", "Second")):
            body = {
                "sessionId": session_id,
                "executionId": execution_id,
                "inputs": {"user_prompt": prompt},
            }
            started = await http.post("/api/sessions/user.session.submit", json=body)
            assert started.status_code == 202 and started.json()["executionId"] == execution_id, (
                started.text
            )
            result = await http.get(f"/api/executions/{execution_id}/result")
            assert result.json()["phase"] == "completed", result.text
            assert result.json()["result"]["nodes_output"] == {"respond": "Mock echo: " + prompt}
            assert (
                result.json()["context"]["execution_id"]
                == result.json()["context"]["root_execution_id"]
                == execution_id
            )
            assert result.json()["context"]["tags"]["credential_user_id"] == "human"
            assert result.json()["context"]["tags"]["hitl_enabled"] is True
            assert (await http.get(f"/api/executions/{execution_id}/children")).json() == []
            assert (
                await http.post("/api/sessions/user.session.submit", json=body)
            ).status_code == 202
            mismatch = {**body, "inputs": {"user_prompt": "different"}}
            assert (
                await http.post("/api/sessions/user.session.submit", json=mismatch)
            ).status_code == 409
        chat = await http.get("/api/sessions/session.chat.get", params=params)
        assert chat.status_code == 200 and chat.json()["blueprint_exists"], chat.text
        assert [message["content"] for message in chat.json()["messages"]] == ["First", "Second"]
        assert (await http.get("/api/sessions/session.state.get", params=params)).json()[
            "nodes_output"
        ] == {"respond": "Mock echo: Second"}
        assert (
            await http.get("/api/sessions/session.status.get", params=params)
        ).json() == "COMPLETED"
        first = await http.get("/api/sessions/session.user.list", params={"limit": 1})
        assert first.json()["pagination"] == {
            "total": 2,
            "limit": 1,
            "offset": 0,
            "has_more": True,
        }, first.text
        second = await http.get("/api/sessions/session.user.list?limit=1&offset=1")
        assert (
            first.json()["sessions"][0]["session_id"] != second.json()["sessions"][0]["session_id"]
        )
        filtered = await http.get(
            "/api/sessions/session.user.list",
            params={"filters": json.dumps({"blueprint_id": "absent"})},
        )
        assert filtered.json()["pagination"]["total"] == 0
        metadata = await http.post(
            "/api/sessions/session.meta",
            json={"sessionId": session_id, "meta": {"title": "Renamed", "hitl_enabled": True}},
        )
        assert metadata.status_code == 200 and metadata.json()["meta"]["title"] == "Renamed", (
            metadata.text
        )
        await http.delete(f"/api/blueprints/{blueprint_id}")
        assert not (await http.get("/api/sessions/session.chat.get", params=params)).json()[
            "blueprint_exists"
        ]
        # Immutable publication survives removal of its authoring blueprint.
        assert (
            await http.post(
                "/api/sessions/user.session.submit",
                json={
                    "sessionId": later_id,
                    "executionId": "later",
                    "inputs": {"user_prompt": "Later"},
                },
            )
        ).status_code == 202
        assert (await http.get("/api/executions/later/result")).json()["result"][
            "nodes_output"
        ] == {"respond": "New snapshot"}
        assert (await http.delete("/api/sessions/session.delete", params=params)).json() == {
            "success": True
        }
        assert (await http.get("/api/sessions/session.chat.get", params=params)).status_code == 404


async def test_chat_session_ownership_and_invalid_filters_do_not_expose_data(secret_settings):
    settings = secret_settings.model_copy(update={"library": True})
    async with library_api(settings, Identity.user("owner")) as http:
        blueprint = await http.post(
            "/api/blueprints", json={"spec": inline_blueprint().model_dump(mode="json")}
        )
        blueprint_id = blueprint.json()["blueprint_id"]
        session = await http.post(
            "/api/sessions/user.session.create", json={"blueprintId": blueprint_id}
        )
        session_id = session.json()
        for filters in (
            {"blueprint_id": {"$ne": None}},
            {"identity.id": "private-filter-value"},
            [],
        ):
            invalid = await http.get(
                "/api/sessions/session.user.list", params={"filters": json.dumps(filters)}
            )
            assert invalid.status_code == 422 and "private-filter-value" not in invalid.text
        spoofed = await http.post(
            "/api/sessions/user.session.create",
            json={"blueprintId": blueprint_id, "userId": "other"},
        )
        assert spoofed.status_code == 422, spoofed.text
    async with library_api(settings, Identity.user("other")) as http:
        assert (await http.get("/api/sessions/session.user.list")).json()["sessions"] == []
        assert (
            await http.post("/api/sessions/user.session.create", json={"blueprintId": blueprint_id})
        ).status_code == 403
        for path in ("session.chat.get", "session.state.get", "session.status.get", "session.meta"):
            assert (
                await http.get("/api/sessions/" + path, params={"sessionId": session_id})
            ).status_code == 403
        assert (
            await http.post(
                "/api/sessions/user.session.submit", json={"sessionId": session_id, "inputs": {}}
            )
        ).status_code == 403
        assert (
            await http.post("/api/sessions/session.cancel", json={"sessionId": session_id})
        ).status_code == 403
        assert (
            await http.delete("/api/sessions/session.delete", params={"sessionId": session_id})
        ).status_code == 403
