"""Opt-in real coding, isolated production checks and durable human acceptance."""

import asyncio
import hashlib
import json
from uuid import uuid4

import pytest
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRun
from mas_plugins.engineering.feature import CodingFeatureResult
from support.feature_api import feature_workflow_access
from support.live_feature import live_feature
from support.review_api import pending_review


@pytest.mark.e2e
@pytest.mark.llm_integration
async def test_live_feature_uses_remote_coding_and_independent_evaluation(
    live_coding_key, remote_backend, mongo_database, redis_uri, tmp_path
):
    owner = Identity.user("reviewer")
    root = uuid4().hex
    async with (
        asyncio.timeout(360),
        live_feature(
            remote_backend, live_coding_key, owner, mongo_database.name, redis_uri, tmp_path
        ) as deployment,
    ):
        api = deployment.api
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": root,
                "program": deployment.programs.feature.model_dump(mode="json"),
                "inputs": {
                    "prompt": "Implement add(a, b) in answer.py. Return a + b.",
                    "acceptance_criteria": [
                        "The add function returns addition for positive, negative and zero inputs."
                    ],
                },
                "workflow_access": [
                    access.model_dump(mode="json")
                    for access in feature_workflow_access(
                        ttl_seconds=300, renewable_for_seconds=300
                    )
                ],
            },
        )
        assert started.status_code == 202, started.text
        design = await pending_review(api.http, root, api.human, api.reviewer, design_number=1)
        children = await api.http.get(f"/api/executions/{root}/children", headers=api.human)
        assert children.status_code == 200
        assert {child["program"]["program_id"] for child in children.json()} == {"design"}
        assert not list((tmp_path / "artifacts").glob("*/metadata.json"))
        response = await api.http.post(
            f"/api/reviews/{design.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "design-approval",
                "expected_revision": design.revision,
                "decision": "approve",
                "data": {"feedback": "Implement this exact design"},
            },
        )
        assert response.status_code == 200, response.text
        final = await pending_review(api.http, root, api.human, api.reviewer, timeout=240)
        assert final.review_id != design.review_id
        assert final.specification.subject["kind"] == "blob-artifact@1"
        candidate = final.specification.subject["identity"]
        source = await api.http.get(
            f"/api/artifacts/{candidate['artifact_id']}/content", headers=api.human
        )
        assert source.status_code == 200
        assert hashlib.sha256(source.content).hexdigest() == candidate["sha256"]
        assert len(source.content) == candidate["size_bytes"]
        checks = [
            CheckRun.model_validate_json(row["data"])
            async for row in mongo_database.verification_check_runs.find({})
        ]
        assert 1 <= len(checks) <= 2
        assert all(check.evidence_recorded and len(check.reports) == 1 for check in checks)
        passed = [check for check in checks if check.observation.verdict == "passed"]
        assert len(passed) == 1 and passed[0].plan.subject.identity == candidate
        assert api.check_binding is not None and api.verifier is not None
        for check in checks:
            assert check.plan.root_execution_id == root
            path = "/api/executions/" + check.observation.external_id
            assert (await api.http.get(path, headers=api.human)).status_code == 403
            observed = await api.http.get(path, headers=api.verifier)
            assert observed.status_code == 200
            assert observed.json()["program"] == api.check_binding.program.model_dump(mode="json")
            assert observed.json()["phase"] == "completed"
        report = await api.http.get(
            "/api/artifacts/" + passed[0].reports[0].content.artifact_id + "/content",
            headers=api.human,
        )
        assert report.status_code == 200
        assert report.json()["verdict"] == "passed"
        assert report.json()["details"] == {"cases": 3, "failures": []}
        response = await api.http.post(
            f"/api/reviews/{final.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "final-approval",
                "expected_revision": final.revision,
                "decision": "approve",
                "data": {"feedback": "Accept the inspected exact candidate"},
            },
        )
        assert response.status_code == 200, response.text
        response = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
        assert response.status_code == 200 and response.json()["phase"] == "completed"
        result = CodingFeatureResult.model_validate(response.json()["result"])
        assert result.outcome == "verified" and result.engineering.attempts == len(checks)
        async with asyncio.timeout(30):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert await mongo_database.workflow_credential_material.count_documents({}) == 3
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
        assert not api.workspace.exists(), "Remote source must not execute in the API workspace"
        # Explicitly audit decoded source too; base64 transport is not secret redaction.
        public = [source.text, report.text, response.text, api.log.read_text()]
        for reference in (deployment.programs.feature, deployment.programs.engineering):
            revision = await api.http.get(
                f"/api/programs/{reference.program_id}/revisions/{reference.revision}",
                headers=api.human,
            )
            assert revision.status_code == 200
            public.append(revision.text)
        if any(deployment.key.get_secret_value() in value for value in public):
            pytest.fail("Private coding credential appeared in public data or logs", pytrace=False)
        (tmp_path / "accepted-result.json").write_text(json.dumps(response.json(), indent=2) + "\n")
        await deployment.release_compute()
        retained_source = await api.http.get(
            f"/api/artifacts/{candidate['artifact_id']}/content", headers=api.human
        )
        retained_report = await api.http.get(
            "/api/artifacts/" + passed[0].reports[0].content.artifact_id + "/content",
            headers=api.human,
        )
        assert retained_source.status_code == retained_report.status_code == 200
        assert (
            retained_source.content == source.content and retained_report.content == report.content
        )
    # All fixture-owned compute is gone; durable candidate/report references remain.
    assert not api.workspace.exists()
