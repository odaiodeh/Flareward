"""Published Engineering runs standalone and as a graph child through real APIs."""

import asyncio
import hashlib
import json
import shutil
from uuid import uuid4

import pytest
from mas.application.execution.models import StartExecution
from mas.core.enums import ResourceCategory
from mas.domain.check_runs import CheckRun
from mas.domain.element_bundles import ResourceDefinition, ResourceKey
from mas.domain.execution.access import WorkflowAccess
from mas.domain.execution.models import ExecutionRecord
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import (
    ApplicationDefinition,
    GraphDefinition,
    OperationStep,
    PathBinding,
    ProgramCallStep,
    ProgramDefinition,
)
from mas.domain.reviews import ReviewRecord
from mas.domain.verification import VerificationSubject
from mas_plugins.artifacts.specification import ELEMENT_SPECIFICATIONS as ARTIFACT_SPECS
from mas_plugins.engineering.program import (
    EngineeringInput,
    EngineeringResult,
)
from mas_plugins.reviews.specification import ELEMENT_SPECIFICATIONS as REVIEW_SPECS
from mas_plugins.verification.specification import ELEMENT_SPECIFICATIONS as VERIFICATION_SPECS
from support.engineering_api import engineering_api
from support.engineering_programs import artifact_candidate_body, engineering_configuration
from support.http_programs import publish_program


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_engineering_repair_and_review_standalone_and_embedded(
    application, mongo_database, redis_uri, tmp_path, profile
):
    for spec in (*ARTIFACT_SPECS, *REVIEW_SPECS, *VERIFICATION_SPECS):
        application.elements.register_spec_class(spec)
    owner = application.owner
    workspace = tmp_path / "workspaces"
    first, repaired = b"candidate requires repair\n", b"candidate verified\n"
    config = engineering_configuration(
        application.elements,
        profile=profile,
        verification_policy="engineering@1",
        runners=("fixture@1",),
        max_polls=20,
        poll_interval_seconds=0.1,
    )
    body = artifact_candidate_body(application.elements, profile)
    definition = ProgramDefinition(
        program_id="engineering-native",
        name="Engineering",
        owner=owner,
        input_schema=EngineeringInput.model_json_schema(),
        output_schema=EngineeringResult.model_json_schema(),
        implementation=ApplicationDefinition(
            implementation="engineering",
            version="1",
            config=config.model_dump(mode="json"),
            children={"implementation": body, "repair": body},
        ),
    )
    access = (
        WorkflowAccess(
            purpose="artifact@1",
            scope={"actions": ["read", "publish"], "namespaces": ["engineering"]},
            ttl_seconds=60,
            renewable_for_seconds=180,
        ),
        WorkflowAccess(
            purpose="review@1",
            scope={"policies": ["release@1"], "actions": ["open", "read", "close"]},
            ttl_seconds=60,
            renewable_for_seconds=180,
        ),
        WorkflowAccess(
            purpose="verification@1",
            scope={"policies": ["engineering@1"], "actions": ["create", "read", "run_check"]},
            ttl_seconds=60,
            renewable_for_seconds=180,
        ),
    )
    async with engineering_api(owner, mongo_database.name, redis_uri, tmp_path) as api:
        http, headers, reviewer_headers = api.http, api.human, api.reviewer
        reference = await publish_program(http, definition, headers=headers)
        stages = tuple(
            ResourceDefinition(
                key=ResourceKey(category=ResourceCategory.OPERATION, rid=stage),
                type_key="fixture_delivery_stage",
                config={"stage": stage},
            )
            for stage in ("jira", "ci", "deployment_validation")
        )
        graph = GraphDefinition(
            resources=stages,
            steps=(
                OperationStep(
                    uid="jira",
                    element=stages[0].key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={"data": PathBinding(path=("values", "task"))},
                    outputs={"values": PathBinding(path=())},
                ),
                ProgramCallStep(
                    uid="engineering",
                    program=reference,
                    inputs={"task": PathBinding(path=("values", "data"))},
                    outputs={"values": PathBinding(path=())},
                ),
                OperationStep(
                    uid="ci",
                    element=stages[1].key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={"data": PathBinding(path=("values",))},
                    outputs={"values": PathBinding(path=())},
                ),
                OperationStep(
                    uid="deployment_validation",
                    element=stages[2].key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={"data": PathBinding(path=("values", "data"))},
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            edges={
                "jira": ("engineering",),
                "engineering": ("ci",),
                "ci": ("deployment_validation",),
            },
            entry="jira",
            exit="deployment_validation",
            inputs={"values": PathBinding(path=())},
            outputs={"result": PathBinding(path=("values", "data"))},
        )
        outer = await publish_program(
            http,
            ProgramDefinition(
                program_id="engineering-outer",
                name="Outer",
                owner=owner,
                implementation=graph,
                input_schema=EngineeringInput.model_json_schema(),
            ),
            headers=headers,
        )
        for run_number, target in enumerate((reference, outer), start=1):
            root_id = uuid4().hex
            workspace_name = hashlib.sha256(root_id.encode()).hexdigest() + "/fixtures"
            fixtures = workspace / workspace_name
            fixtures.mkdir(parents=True)
            (fixtures / "first.txt").write_bytes(first)
            (fixtures / "repair.txt").write_bytes(repaired)
            started = await http.post(
                "/api/executions",
                headers=headers,
                json=StartExecution(
                    program=target,
                    execution_id=root_id,
                    inputs={
                        "task": {"description": "build and review", "workspace": workspace_name}
                    },
                    workflow_access=access,
                ).model_dump(mode="json"),
            )
            assert started.status_code == 202, started.text
            root = started.json()["execution_id"]
            async with asyncio.timeout(40):
                while True:
                    inbox = await http.get("/api/reviews/inbox", headers=reviewer_headers)
                    assert inbox.status_code == 200, inbox.text
                    pending = [
                        ReviewRecord.model_validate(item)
                        for item in inbox.json()["reviews"]
                        if item["root_execution_id"] == root and item["status"] == "pending"
                    ]
                    if pending:
                        break
                    current = await http.get(f"/api/executions/{root}", headers=headers)
                    assert current.json()["phase"] not in {"failed", "cancelled"}, current.text
                    await asyncio.sleep(0.05)
                review = pending[0]
                assert (
                    review.specification.subject["identity"]["sha256"]
                    == hashlib.sha256(repaired).hexdigest()
                )
                decision = await http.post(
                    f"/api/reviews/{review.review_id}/responses",
                    headers=reviewer_headers,
                    json={
                        "key": "approve",
                        "expected_revision": review.revision,
                        "decision": "approve",
                        "data": {"feedback": "checked"},
                    },
                )
                assert decision.status_code == 200, decision.text
                observed = await http.get(f"/api/executions/{root}/result", headers=headers)
                assert observed.status_code == 200, observed.text
            result = ExecutionRecord.model_validate(observed.json())
            assert result.phase == "completed", result.failure
            output = result.result if target == reference else result.result["result"]
            assert output["outcome"] == "verified" and output["attempts"] == 2
            assert output["candidate"]["identity"]["sha256"] == hashlib.sha256(repaired).hexdigest()
            assert output["verification"]["state"]["plan"]["subject"] == output["candidate"]
            subject = VerificationSubject.model_validate(output["candidate"])
            assert output["verification"]["state"]["evidence"][0]["subject_fingerprint"] == (
                subject.fingerprint
            )
            assert output["review"]["review"]["response"]["decision"] == "approve"
            shutil.rmtree(fixtures)
            downloaded = await http.get(
                "/api/artifacts/" + output["candidate"]["identity"]["artifact_id"] + "/content",
                headers=headers,
            )
            assert downloaded.status_code == 200 and downloaded.content == repaired
            assert (
                await mongo_database.verification_check_runs.count_documents({}) == 2 * run_number
            )
            check_runs = [
                CheckRun.model_validate_json(row["data"])
                async for row in mongo_database.verification_check_runs.find({})
            ]
            root_checks = [run for run in check_runs if run.plan.root_execution_id == root]
            assert {run.observation.verdict.value for run in root_checks} == {"failed", "passed"}
            assert all(run.evidence_recorded for run in root_checks)
            if target == outer:
                children = await http.get(f"/api/executions/{root}/children", headers=headers)
                assert children.status_code == 200, children.text
                assert any(
                    child["program"] == reference.model_dump(mode="json")
                    for child in children.json()
                )
            async with asyncio.timeout(15):
                while True:
                    pending_cleanup = (
                        await mongo_database.workflow_credential_material.count_documents(
                            {"$or": [{"retired": False}, {"cleanup_pending": True}]}
                        )
                    )
                    if not pending_cleanup:
                        break
                    await asyncio.sleep(0.05)
            assert (
                await mongo_database.workflow_credential_material.count_documents(
                    {"credential": {"$exists": True}}
                )
                == 0
            )
            public = (
                json.dumps([started.json(), observed.json()])
                + (tmp_path / "engineering-api.log").read_text()
            )
            assert "unifai-review-v1." not in public and "unifai-verification-v1." not in public
            assert "unifai-artifact-workflow-v1." not in public
            assert (
                await mongo_database.artifact_workflow_access_grants.count_documents({})
                == run_number
            )
            assert (
                await mongo_database.artifact_workflow_access_grants.count_documents(
                    {"revoked": False}
                )
                == 0
            )
