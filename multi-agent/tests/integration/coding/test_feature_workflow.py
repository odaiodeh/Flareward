"""Saved production coding restores failed work/reports through the approved feature flow."""

import asyncio
import json
import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRun
from mas.domain.files import InlineFile
from mas.domain.programs.models import ApplicationDefinition, ProgramBody
from mas.domain.verification import CheckRequirement
from mas_plugins.artifacts.specification import ELEMENT_SPECIFICATIONS as ARTIFACTS
from mas_plugins.coding.codex.config import CodexConfig
from mas_plugins.coding.codex.specification import CodexSpec
from mas_plugins.engineering.coding import CodingFileWork
from mas_plugins.engineering.design import DesignProposal
from mas_plugins.engineering.designer import CodingDesignerConfig, CodingDesignWork
from mas_plugins.engineering.feature import CodingFeatureResult
from mas_plugins.engineering.program import EngineeringCandidate
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from mas_plugins.verification.specification import ELEMENT_SPECIFICATIONS as CHECKS
from pydantic import SecretStr
from support.artifacts import inline_content
from support.check_program_publication import CheckProgramSetup
from support.coding_resources import CodingResourceLibrary, saved_coding_candidate
from support.engineering_api import engineering_api, policies
from support.feature_api import feature_workflow_access, publish_feature
from support.python_checks import python_verifier_definition
from support.review_api import pending_review


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_approved_feature_uses_real_coding_adapter_and_restored_check_evidence(
    application, mongo_database, redis_uri, tmp_path, codex_cli, profile
):
    for spec in (*ARTIFACTS, *REVIEWS, *CHECKS, CodexSpec):
        application.elements.register_spec_class(spec)
    policy = policies(application.owner)[0].model_copy(
        update={
            "requirements": (
                CheckRequirement(
                    check="tests@1", verifiers=frozenset({"program-ci"}), requires_reports=True
                ),
            )
        }
    )
    async with engineering_api(
        application.owner,
        mongo_database.name,
        redis_uri,
        tmp_path,
        application_modules=(
            "mas_plugins.engineering.design",
            "mas_plugins.engineering.feature",
            "mas_plugins.engineering.coding",
            "mas_plugins.engineering.designer",
            "mas_plugins.testing.program",
        ),
        element_modules=(
            "mas_plugins.coding.codex.specification",
            "mas_plugins.testing.specification",
        ),
        library=True,
        factory="bootstrap.asgi:create_app",
        verification_policy=policy,
        check_program=CheckProgramSetup(
            python_verifier_definition(Identity.user("trusted-verifier"), profile),
            policies(application.owner)[1].model_copy(update={"verifier": "program-ci"}),
            input_artifact_max_bytes=65_536,
        ),
        environment={
            "PATH": str(codex_cli.parent) + os.pathsep + os.environ.get("PATH", ""),
            "UNIFAI_PYTHON_CHECK_EXECUTION_ENABLED": "true",
            "UNIFAI_PYTHON_CHECK_DIRECTORY": str(tmp_path / "check-workspaces"),
        },
    ) as api:
        config = await saved_coding_candidate(
            api.http,
            api.human,
            config=CodexConfig(
                model="engineering-fixture", api_key=SecretStr("private-test-token")
            ),
            profile=profile,
        )
        source = (
            await api.http.get("/api/resources/" + config.coding.root.rid, headers=api.human)
        ).json()["source"]
        assert (
            await api.http.post(
                "/api/resources/snapshot", headers=api.reviewer, json={"source": source}
            )
        ).status_code == 404
        assert (
            await api.http.post(
                "/api/resources/snapshot",
                headers={**api.human, "Authorization": "Bearer forged"},
                json={"source": source},
            )
        ).status_code == 401
        body = ProgramBody(
            implementation=ApplicationDefinition(
                implementation="coding_file_candidate",
                version="1",
                config=config.model_dump(mode="json"),
            ),
            input_schema=CodingFileWork.model_json_schema(),
            output_schema=EngineeringCandidate.model_json_schema(),
        )
        design_coding = await CodingResourceLibrary(api.http, api.human).coding(
            CodexConfig(model="designer-fixture", api_key=SecretStr("private-test-token")),
            profile,
            name="Feature designer",
        )
        designer = ProgramBody(
            implementation=ApplicationDefinition(
                implementation="coding_designer",
                version="1",
                config=CodingDesignerConfig(
                    coding=design_coding,
                    loader=config.loader,
                    execution=config.execution,
                    artifact_execution=config.artifact_execution,
                ).model_dump(mode="json"),
            ),
            input_schema=CodingDesignWork.model_json_schema(),
            output_schema=DesignProposal.model_json_schema(),
        )
        programs = await publish_feature(
            api.http,
            api.human,
            application.owner,
            application.elements,
            body,
            profile,
            runners=("program@1",),
            designer=designer,
        )
        root = uuid4().hex
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": root,
                "program": programs.feature.model_dump(mode="json"),
                "inputs": {
                    "prompt": "Implement add(a, b) in answer.py",
                    "acceptance_criteria": ["Returns a + b for positive and negative inputs"],
                    "files": [
                        InlineFile(
                            path="README.txt", content=inline_content(b"Interface: add(a, b)")
                        ).model_dump(mode="json")
                    ],
                },
                "workflow_access": [
                    access.model_dump(mode="json") for access in feature_workflow_access()
                ],
            },
        )
        assert started.status_code == 202, started.text
        for number, decision in ((1, "reject"), (2, "approve")):
            design = await pending_review(
                api.http, root, api.human, api.reviewer, design_number=number
            )
            assert not list(api.workspace.rglob("answer.py")) and not list(
                (tmp_path / "artifacts").glob("*/metadata.json")
            )
            assert "Returns a + b" in design.specification.subject["proposal"]["plan"]
            if number == 2:
                assert "Add a failure case" in design.specification.subject["proposal"]["plan"]
            response = await api.http.post(
                f"/api/reviews/{design.review_id}/responses",
                headers=api.reviewer,
                json={
                    "key": "design-response",
                    "expected_revision": design.revision,
                    "decision": decision,
                    "data": {
                        "feedback": "Add a failure case" if number == 1 else "Implement this design"
                    },
                },
            )
            assert response.status_code == 200, response.text
        review = await pending_review(api.http, root, api.human, api.reviewer)
        assert review.specification.subject["kind"] == "blob-artifact@1"
        checks = [
            CheckRun.model_validate_json(row["data"])
            async for row in mongo_database.verification_check_runs.find({})
        ]
        assert len(checks) == 2 and {run.observation.verdict.value for run in checks} == {
            "failed",
            "passed",
        }
        assert all(run.evidence_recorded and len(run.reports) == 1 for run in checks)
        assert api.verifier is not None and api.check_binding is not None
        for run in checks:
            assert run.plan.root_execution_id == root
            execution = run.observation.external_id
            assert (
                await api.http.get(f"/api/executions/{execution}", headers=api.human)
            ).status_code == 403
            owned = await api.http.get(f"/api/executions/{execution}", headers=api.verifier)
            assert owned.status_code == 200, owned.text
            assert owned.json()["program"] == api.check_binding.program.model_dump(mode="json")
            assert owned.json()["phase"] == "completed"
        failed = next(run for run in checks if run.observation.verdict == "failed")
        report = await api.http.get(
            "/api/artifacts/" + failed.reports[0].content.artifact_id + "/content",
            headers=api.human,
        )
        assert report.status_code == 200 and report.json()["details"]["failures"]
        all_workspaces = [path.parent for path in api.workspace.rglob("started")]
        planners = [path for path in all_workspaces if (path / "design-request.json").exists()]
        assert len(planners) == 2
        assert all(
            (path / "README.txt").read_bytes() == b"Interface: add(a, b)" for path in planners
        )
        workspaces = [path for path in all_workspaces if (path / "answer.py").exists()]
        assert len(workspaces) == 2 and workspaces[0] != workspaces[1]
        restored = [path for path in workspaces if (path / ".unifai/reports").is_dir()]
        assert len(restored) == 1
        assert (
            restored[0] / ".unifai/reports" / failed.reports[0].content.artifact_id
        ).read_bytes() == report.content
        assert all(not Path((path / "home").read_text()).exists() for path in all_workspaces)
        accepted = await api.http.post(
            f"/api/reviews/{review.review_id}/responses",
            headers=api.reviewer,
            json={
                "key": "final-approval",
                "expected_revision": review.revision,
                "decision": "approve",
                "data": {"feedback": "Checked source and independent tests"},
            },
        )
        assert accepted.status_code == 200, accepted.text
        observed = await api.http.get(f"/api/executions/{root}/result", headers=api.human)
        assert observed.status_code == 200 and observed.json()["phase"] == "completed", (
            observed.text
        )
        result = CodingFeatureResult.model_validate(observed.json()["result"])
        assert result.outcome == "verified" and result.engineering.attempts == 2
        assert result.design.design.number == 2
        shutil.rmtree(api.workspace)
        downloaded = await api.http.get(
            "/api/artifacts/" + result.engineering.candidate.identity["artifact_id"] + "/content",
            headers=api.human,
        )
        assert (
            downloaded.status_code == 200
            and downloaded.content == b"def add(a, b):\n    return a + b\n"
        )
        async with asyncio.timeout(15):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert await mongo_database.workflow_credential_material.count_documents({}) == 3
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
        public = json.dumps(observed.json()) + api.log.read_text()
        assert "private-test-token" not in public and "unifai-artifact-workflow-v1." not in public
