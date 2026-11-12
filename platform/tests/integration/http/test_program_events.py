"""External deliveries use the same native operations, child Programs and human workbench."""

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
from support.http_programs import publish_program
from support.managed_access import managed_access_api
from support.managed_workflow import review_verification_graph, workflow_requirements
from support.review_programs import review_definition
from support.verification import verification_request

from lumora.executions.domain.models import ExecutionRecord
from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramDefinition
from lumora.services.access.issuance import CredentialReservation
from lumora.services.reviews.domain.models import ReviewRecord
from plugins.human_review.elements.specification import (
    ELEMENT_SPECIFICATIONS as REVIEW_SPECIFICATIONS,
)
from plugins.verification.elements.specification import (
    ELEMENT_SPECIFICATIONS as VERIFICATION_SPECIFICATIONS,
)


async def test_event_rotation_requires_human_and_never_returns_secrets_from_inspection(
    mongo_database, redis_uri, tmp_path
):
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        program = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="event-rotation",
                name="Rotation",
                owner=api.owner,
                implementation=CustomCoordinatorDefinition(implementation="greeting", version="1"),
            ),
            headers=api.human,
        )
        created = await api.http.post(
            "/api/program-events/sources",
            headers=api.human,
            json={
                "name": "Rotation",
                "program": program.model_dump(mode="json"),
                "event_type": "issue@1",
                "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            },
        )
        assert created.status_code == 201, created.text
        issued = created.json()
        path = f"/api/program-events/sources/{issued['source']['source_id']}"
        denied = await api.http.post(
            path + "/credential",
            headers={"Authorization": "Bearer " + issued["credential"]},
            json={"expected_revision": 0},
        )
        assert denied.status_code == 401
        rotated = await api.http.post(
            path + "/credential", headers=api.human, json={"expected_revision": 0}
        )
        assert rotated.status_code == 200 and rotated.headers["Cache-Control"] == "no-store"
        credential = rotated.json()["credential"]
        settings = await api.http.get(path + "/settings", headers=api.human)
        assert settings.json()["credential_revision"] == 1
        assert credential not in settings.text and issued["credential"] not in settings.text
        assert credential not in api.log.read_text()


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_event_source_runs_typed_operations_and_review_with_private_scoped_authority(
    application, mongo_database, redis_uri, tmp_path, profile
):
    for spec in (*REVIEW_SPECIFICATIONS, *VERIFICATION_SPECIFICATIONS):
        application.elements.register_spec_class(spec)
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        review = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="event-review",
                name="Review",
                owner=api.owner,
                implementation=review_definition(application.elements, profile),
            ),
            headers=api.human,
        )
        program = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="event-workflow",
                name="Workflow",
                owner=api.owner,
                implementation=review_verification_graph(review, profile),
            ),
            headers=api.human,
        )
        request = {
            "name": "Issue intake",
            "program": program.model_dump(mode="json"),
            "event_type": "issue@1",
            "input_schema": {
                "type": "object",
                "required": ["subject"],
                "additionalProperties": False,
                "properties": {"subject": {"type": "object"}},
            },
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
            "workflow_access": [item.model_dump(mode="json") for item in workflow_requirements()],
        }
        denied = await api.http.post(
            "/api/program-events/sources",
            headers={**api.human, "Authorization": "Bearer workflow-is-not-human"},
            json=request,
        )
        assert denied.status_code == 401, denied.text
        assert await mongo_database.program_event_sources.count_documents({}) == 0
        created = await api.http.post(
            "/api/program-events/sources", headers=api.human, json=request
        )
        assert created.status_code == 201, created.text
        assert created.headers["Cache-Control"] == "no-store"
        issued = created.json()
        source = issued["source"]
        bearer = {"Authorization": "Bearer " + issued["credential"]}
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        event = {
            "event_id": "issue-42",
            "event_type": "issue@1",
            "inputs": {"subject": verification_request().subject.model_dump(mode="json")},
        }
        for headers, body, status in (
            (api.human, event, 401),
            ({**api.human, "Authorization": "Bearer invalid"}, event, 401),
            (bearer, {**event, "event_type": "other@1"}, 403),
            (bearer, {**event, "inputs": {}}, 422),
        ):
            refused = await api.http.post(
                "/api/program-events/deliveries", headers=headers, json=body
            )
            assert refused.status_code == status, refused.text
        submitted = await asyncio.gather(
            *(
                api.http.post("/api/program-events/deliveries", headers=bearer, json=event)
                for _ in range(8)
            )
        )
        assert all(response.status_code == 202 for response in submitted), [
            r.text for r in submitted
        ]
        roots = {response.json()["execution_id"] for response in submitted}
        assert len(roots) == 1
        root = roots.pop()
        async with asyncio.timeout(20):
            while True:
                inbox = await api.http.get("/api/reviews/inbox", headers=api.reviewer)
                assert inbox.status_code == 200, inbox.text
                if inbox.json()["reviews"]:
                    pending = ReviewRecord.model_validate(inbox.json()["reviews"][0])
                    break
                await asyncio.sleep(0.05)
        assert pending.root_execution_id == root
        assert await mongo_database.workflow_credential_material.count_documents({}) == 2
        assert await mongo_database.program_reviews.count_documents({}) == 1
        response = await api.http.get(f"/api/executions/{root}", headers=api.human)
        assert response.status_code == 200, response.text
        record = ExecutionRecord.model_validate(response.json())
        assert record.program == program
        assert record.workflow_access_approval.approved_by.owns(api.owner)
        assert record.context.tags["event"] == {
            "source_id": source["source_id"],
            "event_id": event["event_id"],
            "event_type": "issue@1",
        }
        # A delivery key grants no human source-management authority, even with a cookie.
        assert (
            await api.http.get(
                f"/api/program-events/sources/{source['source_id']}",
                headers={**api.human, **bearer},
            )
        ).status_code == 401
        conflict = await api.http.post(
            "/api/program-events/deliveries",
            headers=bearer,
            json={
                **event,
                "inputs": {
                    "subject": verification_request(digest="b" * 64).subject.model_dump(mode="json")
                },
            },
        )
        assert conflict.status_code == 409, conflict.text
        revoked = await api.http.delete(
            f"/api/program-events/sources/{source['source_id']}", headers=api.human
        )
        assert revoked.status_code == 204, revoked.text
        assert (
            await api.http.post(
                "/api/program-events/deliveries",
                headers=bearer,
                json={**event, "event_id": "issue-43"},
            )
        ).status_code == 401
        assert (
            await api.http.post(
                f"/api/reviews/{pending.review_id}/responses",
                headers=api.reviewer,
                json={
                    "key": "event-reviewed",
                    "expected_revision": pending.revision,
                    "decision": "approve",
                    "data": {"feedback": "Reviewed the delivered candidate"},
                },
            )
        ).status_code == 200
        result = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["result"]["review"]["response"]["decision"] == "approve"
        async with asyncio.timeout(10):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        rows = [row async for row in mongo_database.workflow_credential_material.find({})]
        assert all(
            CredentialReservation.model_validate_json(row["data"]).root_execution_id == root
            for row in rows
        )
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
        registration = await mongo_database.program_event_sources.find_one({})
        assert issued["credential"] not in registration["data"]
        observed = json.dumps([r.json() for r in submitted] + [result.json()]) + api.log.read_text()
        assert issued["credential"] not in observed
        assert "lumora-review-v1." not in observed and "lumora-verification-v1." not in observed


async def test_event_schema_and_program_contract_errors_are_private_before_admission(
    mongo_database, redis_uri, tmp_path
):
    marker = "private-unparsed-event-value"
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        program = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="event-contract",
                name="Contract",
                owner=api.owner,
                implementation=CustomCoordinatorDefinition(implementation="greeting", version="1"),
                input_schema={"type": "object", "required": ["name"]},
            ),
            headers=api.human,
        )
        request = {
            "name": "Contract source",
            "program": program.model_dump(mode="json"),
            "event_type": "issue@1",
            "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }
        for change in (
            {"input_schema": {"type": marker}},
            {"name": marker, "expires_at": (datetime.now(UTC) - timedelta(hours=1)).isoformat()},
            {"workflow_access": [{"purpose": "review@1", "scope": {"credential": marker}}]},
        ):
            refused = await api.http.post(
                "/api/program-events/sources", headers=api.human, json={**request, **change}
            )
            assert refused.status_code == 422, refused.text
            assert marker not in refused.text
        assert await mongo_database.program_event_sources.count_documents({}) == 0
        created = await api.http.post(
            "/api/program-events/sources", headers=api.human, json=request
        )
        assert created.status_code == 201, created.text
        issued = created.json()
        bearer = {"Authorization": "Bearer " + issued["credential"]}
        refused = await api.http.post(
            "/api/program-events/deliveries",
            headers=bearer,
            json={"event_id": "invalid", "event_type": "issue@1", "inputs": {"unexpected": marker}},
        )
        assert refused.status_code == 422 and marker not in refused.text
        assert await mongo_database.program_executions.count_documents({}) == 0
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        listed = await api.http.get("/api/program-events/sources", headers=api.human)
        assert listed.status_code == 200
        assert issued["credential"] not in listed.text and "secret_sha256" not in listed.text
        assert (
            await api.http.get(
                "/api/program-events/sources/" + issued["source"]["source_id"], headers=bearer
            )
        ).status_code == 401
        assert marker not in api.log.read_text()
