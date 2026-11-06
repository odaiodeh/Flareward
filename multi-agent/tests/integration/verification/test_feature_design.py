"""Native design revisions use assigned human decisions and automatic root authority."""

import asyncio
import json
from uuid import uuid4

import pytest
from mas.domain.execution.access import WorkflowAccess
from mas.domain.programs.models import ProgramDefinition
from mas_plugins.engineering.design import DesignResult, FeatureRequest
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS
from support.feature_design import design_definition, designer_body
from support.http_programs import publish_program
from support.managed_access import managed_access_api
from support.review_api import pending_review


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("decision", ["approve", "reject"])
async def test_native_feature_design_revisions_preserve_exact_review_and_root_authority(
    application, mongo_database, redis_uri, tmp_path, profile, decision
):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    async with managed_access_api(
        mongo_database.name,
        redis_uri,
        tmp_path,
        application_modules=("mas_plugins.engineering.design", "support.feature_design"),
    ) as api:
        body = designer_body()
        designer = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="designer",
                name="Design proposer",
                owner=api.owner,
                implementation=body.implementation,
                input_schema=body.input_schema,
                output_schema=body.output_schema,
            ),
            headers=api.human,
        )
        program = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="feature-design",
                name="Feature design",
                owner=api.owner,
                implementation=design_definition(application.elements, profile, designer=designer),
                input_schema=FeatureRequest.model_json_schema(),
                output_schema=DesignResult.model_json_schema(),
            ),
            headers=api.human,
        )
        request = FeatureRequest(
            task={"description": "Add a validated operation"},
            acceptance_criteria=("Valid input succeeds", "Invalid input is rejected"),
        )
        root = uuid4().hex
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": root,
                "program": program.model_dump(mode="json"),
                "inputs": request.model_dump(mode="json"),
                "workflow_access": [
                    WorkflowAccess(
                        purpose="review@1",
                        scope={"policies": ["release@1"], "actions": ["open", "read", "close"]},
                        ttl_seconds=60,
                        renewable_for_seconds=180,
                    ).model_dump(mode="json")
                ],
            },
        )
        assert started.status_code == 202, started.text
        first = await pending_review(api.http, root, api.human, api.reviewer, design_number=1)
        assert first.specification.subject["request"] == request.model_dump(mode="json")
        children = await api.http.get(f"/api/executions/{root}/children", headers=api.human)
        assert children.status_code == 200, children.text
        assert len(children.json()) == 1 and children.json()[0]["phase"] == "completed"
        assert children.json()[0]["program"] == designer.model_dump(mode="json")

        path = f"/api/reviews/{first.review_id}/responses"
        rejection = {
            "key": "first-decision",
            "expected_revision": first.revision,
            "decision": "reject",
            "data": {"feedback": "Include the invalid-input case"},
        }
        assert (await api.http.post(path, headers=api.human, json=rejection)).status_code == 404
        accepted = await api.http.post(path, headers=api.reviewer, json=rejection)
        assert accepted.status_code == 200, accepted.text
        assert (await api.http.post(path, headers=api.reviewer, json=rejection)).json()[
            "response"
        ] == accepted.json()["response"]
        second = await pending_review(api.http, root, api.human, api.reviewer, design_number=2)
        assert second.review_id != first.review_id
        assert second.specification.fingerprint != first.specification.fingerprint
        assert second.specification.subject["request"] == request.model_dump(mode="json")
        assert "Include the invalid-input case" in second.specification.subject["proposal"]["plan"]
        stale = await api.http.post(
            path, headers=api.reviewer, json={**rejection, "decision": "approve"}
        )
        assert stale.status_code == 409, stale.text
        current = await api.http.get(f"/api/executions/{root}", headers=api.human)
        assert current.json()["phase"] not in {"completed", "failed", "cancelled"}
        final = await api.http.post(
            f"/api/reviews/{second.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "second-decision",
                "expected_revision": second.revision,
                "decision": decision,
                "data": {"feedback": "Reviewed revision two"},
            },
        )
        assert final.status_code == 200, final.text
        observed = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
        assert observed.status_code == 200 and observed.json()["phase"] == "completed", (
            observed.text
        )
        result = DesignResult.model_validate(observed.json()["result"])
        assert result.outcome == ("approved" if decision == "approve" else "revisions_exhausted")
        assert result.design.number == 2 and result.review.review.review_id == second.review_id
        assert result.review.review.specification.subject == result.design.model_dump(mode="json")
        async with asyncio.timeout(15):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert await mongo_database.review_access_grants.count_documents({"revoked": False}) == 0
        assert "unifai-review-v1." not in json.dumps(observed.json()) + api.log.read_text()
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
