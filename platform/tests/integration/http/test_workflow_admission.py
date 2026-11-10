"""Human-authorized manual/Session roots provision through actual Mongo/API/native receivers."""

import asyncio
import json

import pytest
from support.http_programs import publish_program
from support.managed_access import managed_access_api
from support.review_programs import review_definition
from support.verification import verification_request
from support.verification_programs import verification_resources

from lumora.executions.domain.access import WorkflowAccess
from lumora.executions.domain.models import ExecutionRecord
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.models import (
    GraphDefinition,
    OperationStep,
    PathBinding,
    ProgramDefinition,
)
from lumora.resources.domain.bundles import ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.reviews.domain.models import ReviewRecord
from plugins.human_review.elements.specification import (
    ELEMENT_SPECIFICATIONS as REVIEW_SPECIFICATIONS,
)
from plugins.verification.elements.specification import (
    ELEMENT_SPECIFICATIONS as VERIFICATION_SPECIFICATIONS,
)


@pytest.mark.parametrize("purpose", ["review", "verification"])
@pytest.mark.parametrize("session", [False, True])
@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_admission_provisions_and_retires_native_root_access(
    application, mongo_database, redis_uri, tmp_path, purpose, session, profile
):
    for spec in (*REVIEW_SPECIFICATIONS, *VERIFICATION_SPECIFICATIONS):
        application.elements.register_spec_class(spec)
    if purpose == "review":
        implementation = review_definition(application.elements, profile)
        inputs = {"subject": {"candidate": "admitted-candidate"}}
        actions = ["open", "read", "close"]
    else:
        implementation = GraphDefinition(
            resources=verification_resources()[:2],
            steps=(
                OperationStep(
                    uid="request",
                    element=ResourceKey(category=ResourceCategory.OPERATION, rid="request"),
                    execution=ExecutionSelection(profile=profile),
                    inputs={
                        "subject": PathBinding(path=("values", "subject")),
                        "policy": PathBinding(path=("values", "policy")),
                    },
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            entry="request",
            exit="request",
            inputs={"values": PathBinding(path=())},
            outputs={"result": PathBinding(path=("values",))},
        )
        inputs = {
            "subject": verification_request().subject.model_dump(mode="json"),
            "policy": "release@1",
        }
        actions = ["create", "read", "cancel"]
    requirement = WorkflowAccess(
        purpose=purpose + "@1",
        scope={"policies": ["release@1"], "actions": actions},
        ttl_seconds=60,
        renewable_for_seconds=180,
    )
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        reference = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="managed-root",
                name="Managed root",
                owner=api.owner,
                implementation=implementation,
            ),
            headers=api.human,
        )
        root = "automatic-root"
        body = {
            "execution_id": root,
            "inputs": inputs,
            "workflow_access": [requirement.model_dump(mode="json")],
        }
        if session:
            created = await api.http.post(
                "/api/sessions",
                headers=api.human,
                json={"program": reference.model_dump(mode="json")},
            )
            assert created.status_code == 201, created.text
            endpoint = f"/api/sessions/{created.json()['run_id']}/executions"
        else:
            endpoint = "/api/executions"
            body["program"] = reference.model_dump(mode="json")
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        denied = await api.http.post(
            endpoint,
            headers={**api.human, "Authorization": "Bearer untrusted-workflow-token"},
            json=body,
        )
        assert denied.status_code == 401, denied.text
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        invalid = await api.http.post(
            endpoint,
            headers=api.human,
            json={
                **body,
                "workflow_access": [
                    {
                        **requirement.model_dump(mode="json"),
                        "scope": {"credential": "private-unparsed-workflow-value"},
                    }
                ],
            },
        )
        assert invalid.status_code == 422, invalid.text
        assert "private-unparsed-workflow-value" not in invalid.text
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        assert (await api.http.get(f"/api/executions/{root}", headers=api.human)).status_code == 404
        submitted = await api.http.post(endpoint, headers=api.human, json=body)
        assert submitted.status_code == 202, submitted.text
        observed = await api.http.get(f"/api/executions/{root}", headers=api.human)
        assert observed.status_code == 200, observed.text
        record = ExecutionRecord.model_validate(observed.json())
        approval = record.workflow_access_approval
        assert approval is not None and approval.approved_by.owns(api.owner)
        assert approval.owner.owns(api.owner) and approval.root_execution_id == root
        assert approval.requirements == (requirement,)
        if session:
            assert submitted.json()["workflow_access_approval"] == approval.model_dump(mode="json")
        if purpose == "review":
            async with asyncio.timeout(20):
                while True:
                    inbox = await api.http.get("/api/reviews/inbox", headers=api.reviewer)
                    assert inbox.status_code == 200, inbox.text
                    if inbox.json()["reviews"]:
                        review = ReviewRecord.model_validate(inbox.json()["reviews"][0])
                        break
                    current = await api.http.get(f"/api/executions/{root}", headers=api.human)
                    assert current.status_code == 200, current.text
                    assert current.json()["phase"] not in {"completed", "failed", "cancelled"}, (
                        current.text
                    )
                    await asyncio.sleep(0.05)
            assert review.root_execution_id == root
            decision = await api.http.post(
                f"/api/reviews/{review.review_id}/responses",
                headers=api.reviewer,
                json={
                    "key": "admitted-review",
                    "expected_revision": review.revision,
                    "decision": "approve",
                    "data": {"feedback": "Reviewed the exact admitted candidate"},
                },
            )
            assert decision.status_code == 200, decision.text
        result = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
        retry = await api.http.post(endpoint, headers=api.human, json=body)
        assert retry.status_code == 202, retry.text
        assert await mongo_database.workflow_credential_material.count_documents({}) == 1
        async with asyncio.timeout(10):
            while True:
                material = await mongo_database.workflow_credential_material.find_one({})
                if material["retired"] and not material["cleanup_pending"]:
                    break
                await asyncio.sleep(0.05)
        assert "credential" not in material
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
        portable = json.dumps([submitted.json(), result.json()]) + api.log.read_text()
        assert "lumora-review-v1." not in portable and "lumora-verification-v1." not in portable
