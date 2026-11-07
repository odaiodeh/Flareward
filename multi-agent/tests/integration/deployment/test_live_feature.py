"""Opt-in unchanged Engineering reuse with real coding and isolated production checks."""

import asyncio
import hashlib
import json
from uuid import uuid4

import pytest
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRun
from mas.domain.reviews import ReviewRecord
from mas_plugins.engineering.feature import CodingFeatureResult
from mas_plugins.engineering.program import EngineeringResult
from support.engineering_api import EngineeringAPI
from support.feature_api import feature_workflow_access
from support.live_feature import live_feature
from support.review_api import pending_review


async def approve(api: EngineeringAPI, review: ReviewRecord, key: str, feedback: str) -> None:
    response = await api.http.post(
        f"/api/reviews/{review.review_id}/responses",
        headers=api.reviewer,
        json={
            "key": key,
            "expected_revision": review.revision,
            "decision": "approve",
            "data": {"feedback": feedback},
        },
    )
    assert response.status_code == 200, response.text


@pytest.mark.e2e
@pytest.mark.llm_integration
async def test_live_engineering_revision_runs_unchanged_independently_and_nested(
    live_coding_key, remote_backend, mongo_database, redis_uri, tmp_path
):
    owner = Identity.user("reviewer")
    async with (
        asyncio.timeout(600),
        live_feature(
            remote_backend, live_coding_key, owner, mongo_database.name, redis_uri, tmp_path
        ) as deployment,
    ):
        api = deployment.api
        path = (
            f"/api/programs/{deployment.programs.engineering.program_id}/revisions/"
            f"{deployment.programs.engineering.revision}"
        )
        published = await api.http.get(path, headers=api.human)
        assert published.status_code == 200
        feature_revision = await api.http.get(
            f"/api/programs/{deployment.programs.feature.program_id}/revisions/"
            f"{deployment.programs.feature.revision}",
            headers=api.human,
        )
        assert feature_revision.status_code == 200
        task = {"prompt": "Implement add(a, b) in answer.py. Return a + b."}
        retained = []
        results = []
        plan_ids = set()
        for reference, inputs in (
            (deployment.programs.engineering, {"task": task}),
            (
                deployment.programs.feature,
                {
                    **task,
                    "acceptance_criteria": [
                        "The add function returns addition for positive, negative and zero inputs."
                    ],
                },
            ),
        ):
            root = uuid4().hex
            artifacts_before = set((tmp_path / "artifacts").glob("*/metadata.json"))
            started = await api.http.post(
                "/api/executions",
                headers=api.human,
                json={
                    "execution_id": root,
                    "program": reference.model_dump(mode="json"),
                    "inputs": inputs,
                    "workflow_access": [
                        access.model_dump(mode="json")
                        for access in feature_workflow_access(
                            ttl_seconds=300, renewable_for_seconds=300
                        )
                    ],
                },
            )
            assert started.status_code == 202, started.text
            if reference == deployment.programs.feature:
                design = await pending_review(
                    api.http, root, api.human, api.reviewer, design_number=1
                )
                children = await api.http.get(f"/api/executions/{root}/children", headers=api.human)
                assert children.status_code == 200
                assert {child["program"]["program_id"] for child in children.json()} == {"design"}
                assert set((tmp_path / "artifacts").glob("*/metadata.json")) == artifacts_before
                await approve(api, design, "design-approval", "Implement this exact design")
            final = await pending_review(api.http, root, api.human, api.reviewer, timeout=240)
            assert final.specification.subject["kind"] == "blob-artifact@1"
            candidate = final.specification.subject["identity"]
            source = await api.http.get(
                f"/api/artifacts/{candidate['artifact_id']}/content", headers=api.human
            )
            assert source.status_code == 200
            assert hashlib.sha256(source.content).hexdigest() == candidate["sha256"]
            assert len(source.content) == candidate["size_bytes"]
            all_checks = [
                CheckRun.model_validate_json(row["data"])
                async for row in mongo_database.verification_check_runs.find({})
            ]
            checks = [check for check in all_checks if check.plan.root_execution_id == root]
            assert 1 <= len(checks) <= 2
            assert all(check.evidence_recorded and len(check.reports) == 1 for check in checks)
            passed = [check for check in checks if check.observation.verdict == "passed"]
            assert len(passed) == 1 and passed[0].plan.subject.identity == candidate
            assert api.check_binding is not None and api.verifier is not None
            for check in checks:
                assert check.plan.plan_id not in plan_ids
                path = "/api/executions/" + check.observation.external_id
                assert (await api.http.get(path, headers=api.human)).status_code == 403
                observed = await api.http.get(path, headers=api.verifier)
                assert observed.status_code == 200
                assert observed.json()["program"] == api.check_binding.program.model_dump(
                    mode="json"
                )
                assert observed.json()["phase"] == "completed"
            plan_ids.update(check.plan.plan_id for check in checks)
            report_ref = passed[0].reports[0].content
            report = await api.http.get(
                "/api/artifacts/" + report_ref.artifact_id + "/content", headers=api.human
            )
            assert report.status_code == 200
            assert hashlib.sha256(report.content).hexdigest() == report_ref.sha256
            assert len(report.content) == report_ref.size_bytes
            assert report.json()["verdict"] == "passed"
            assert report.json()["details"] == {"cases": 3, "failures": []}
            await approve(api, final, "final-approval", "Accept the inspected exact candidate")
            response = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
            assert response.status_code == 200 and response.json()["phase"] == "completed"
            if reference == deployment.programs.feature:
                result = CodingFeatureResult.model_validate(response.json()["result"])
                assert result.outcome == "verified"
                engineering = result.engineering
                children = await api.http.get(f"/api/executions/{root}/children", headers=api.human)
                assert children.status_code == 200
                nested = [
                    child
                    for child in children.json()
                    if child["program"] == deployment.programs.engineering.model_dump(mode="json")
                ]
                assert len(nested) == 1 and nested[0]["phase"] == "completed"
                assert nested[0]["context"]["root_execution_id"] == root
            else:
                engineering = EngineeringResult.model_validate(response.json()["result"])
                observed = await api.http.get(f"/api/executions/{root}", headers=api.human)
                assert observed.status_code == 200
                assert observed.json()["program"] == reference.model_dump(mode="json")
                assert observed.json()["context"]["root_execution_id"] == root
            assert engineering is not None and engineering.outcome == "verified"
            assert engineering.attempts == len(checks)
            assert engineering.review.review.root_execution_id == root
            assert (
                await api.http.get(
                    f"/api/programs/{deployment.programs.engineering.program_id}/revisions/"
                    f"{deployment.programs.engineering.revision}",
                    headers=api.human,
                )
            ).json() == published.json()
            # Audit decoded content too; base64 transport is not redaction.
            public = [
                source.text,
                report.text,
                response.text,
                api.log.read_text(),
                published.text,
                feature_revision.text,
            ]
            if any(deployment.key.get_secret_value() in value for value in public):
                pytest.fail(
                    "Private coding credential appeared in public data or logs", pytrace=False
                )
            retained.extend(
                ((candidate, source.content), (report_ref.model_dump(mode="json"), report.content))
            )
            results.append(
                {
                    "execution_id": root,
                    "program": reference.model_dump(mode="json"),
                    **response.json(),
                }
            )
        async with asyncio.timeout(30):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        material = [row async for row in mongo_database.workflow_credential_material.find({})]
        assert len(material) == 6 and all("credential" not in row for row in material)
        roots = [json.loads(row["data"])["root_execution_id"] for row in material]
        assert all(roots.count(result["execution_id"]) == 3 for result in results)
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
        assert not api.workspace.exists(), "Remote source must not execute in the API workspace"
        (tmp_path / "accepted-results.json").write_text(json.dumps(results, indent=2) + "\n")
        await deployment.release_compute()
        for reference, content in retained:
            downloaded = await api.http.get(
                "/api/artifacts/" + reference["artifact_id"] + "/content", headers=api.human
            )
            assert downloaded.status_code == 200 and downloaded.content == content
    # All fixture-owned compute is gone; durable candidate/report references remain.
    assert not api.workspace.exists()
