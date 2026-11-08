"""Native design approval gates Engineering; exact fixture-byte checks remain independent."""

import asyncio
import hashlib
import shutil
from uuid import uuid4

import pytest
from mas.domain.execution.access import WorkflowAccess
from mas_plugins.artifacts.specification import ELEMENT_SPECIFICATIONS as ARTIFACTS
from mas_plugins.engineering.feature import CodingFeatureResult
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from mas_plugins.verification.specification import ELEMENT_SPECIFICATIONS as CHECKS
from support.engineering_api import engineering_api
from support.engineering_programs import artifact_candidate_body
from support.feature_api import publish_feature
from support.review_api import pending_review


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("approved", [True, False])
async def test_native_coding_feature_starts_engineering_only_after_exact_design_approval(
    application, mongo_database, redis_uri, tmp_path, profile, approved
):
    for spec in (*ARTIFACTS, *REVIEWS, *CHECKS):
        application.elements.register_spec_class(spec)
    root = uuid4().hex
    workspace = hashlib.sha256(root.encode()).hexdigest() + "/fixtures"
    body = artifact_candidate_body(application.elements, profile, workspace=workspace)
    async with engineering_api(
        application.owner,
        mongo_database.name,
        redis_uri,
        tmp_path,
        application_modules=(
            "mas_plugins.engineering.design",
            "mas_plugins.engineering.feature",
            "support.feature_design",
        ),
    ) as api:
        programs = await publish_feature(
            api.http, api.human, application.owner, application.elements, body, profile
        )
        implementation, feature = programs.engineering, programs.feature
        fixtures = api.workspace / workspace
        fixtures.mkdir(parents=True)
        (fixtures / "first.txt").write_bytes(b"candidate requires repair\n")
        (fixtures / "repair.txt").write_bytes(b"candidate verified\n")
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": root,
                "program": feature.model_dump(mode="json"),
                "inputs": {
                    "prompt": "Implement addition",
                    "acceptance_criteria": ["Handles negative numbers"],
                },
                "workflow_access": [
                    WorkflowAccess(
                        purpose=purpose,
                        scope=scope,
                        ttl_seconds=60,
                        renewable_for_seconds=180,
                    ).model_dump(mode="json")
                    for purpose, scope in (
                        (
                            "review@1",
                            {"policies": ["release@1"], "actions": ["open", "read", "close"]},
                        ),
                        (
                            "verification@1",
                            {
                                "policies": ["engineering@1"],
                                "actions": ["create", "read", "run_check"],
                            },
                        ),
                        (
                            "artifact@1",
                            {"namespaces": ["engineering"], "actions": ["read", "publish"]},
                        ),
                    )
                ],
            },
        )
        assert started.status_code == 202, started.text
        for number in (1, 2):
            review = await pending_review(
                api.http, root, api.human, api.reviewer, design_number=number
            )
            children = await api.http.get(f"/api/executions/{root}/children", headers=api.human)
            assert children.status_code == 200, children.text
            assert not any(
                child["program"] == implementation.model_dump(mode="json")
                for child in children.json()
            )
            assert await mongo_database.verification_check_runs.count_documents({}) == 0
            assert not list((tmp_path / "artifacts").glob("*/metadata.json"))
            response = await api.http.post(
                f"/api/reviews/{review.review_id}/responses",
                headers=api.reviewer,
                json={
                    "key": f"design-{number}",
                    "expected_revision": review.revision,
                    "decision": "approve" if number == 2 and approved else "reject",
                    "data": {"feedback": "Cover the negative-number case"},
                },
            )
            assert response.status_code == 200, response.text
        if approved:
            final = await pending_review(api.http, root, api.human, api.reviewer)
            assert final.specification.subject["candidate"]["kind"] == "blob-artifact@1"
            assert (
                final.specification.subject["candidate"]["identity"]["sha256"]
                == hashlib.sha256(b"candidate verified\n").hexdigest()
            )
            response = await api.http.post(
                f"/api/reviews/{final.review_id}/responses",
                headers=api.reviewer,
                json={
                    "key": "final-review",
                    "expected_revision": final.revision,
                    "decision": "approve",
                    "data": {"feedback": "Checked exact candidate"},
                },
            )
            assert response.status_code == 200, response.text
        observed = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
        assert observed.status_code == 200 and observed.json()["phase"] == "completed", (
            observed.text
        )
        result = CodingFeatureResult.model_validate(observed.json()["result"])
        assert result.outcome == ("verified" if approved else "design_unsatisfied")
        children = await api.http.get(f"/api/executions/{root}/children", headers=api.human)
        assert children.status_code == 200, children.text
        assert sum(
            child["program"] == implementation.model_dump(mode="json") for child in children.json()
        ) == int(approved)
        assert await mongo_database.verification_check_runs.count_documents({}) == (
            2 if approved else 0
        )
        if approved:
            assert result.engineering.attempts == 2
            shutil.rmtree(fixtures)
            response = await api.http.get(
                "/api/artifacts/"
                + result.engineering.candidate.identity["artifact_id"]
                + "/content",
                headers=api.human,
            )
            assert response.status_code == 200 and response.content == b"candidate verified\n"
        else:
            assert result.engineering is None
        async with asyncio.timeout(15):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert await mongo_database.workflow_credential_material.count_documents({}) == 3
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
