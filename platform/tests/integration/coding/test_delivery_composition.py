"""Delivery -> Repeat -> graph -> Engineering -> real coding/check/review effects."""

import asyncio
import hashlib
import os
import shutil
from uuid import uuid4

import pytest
from pydantic import SecretStr
from support.check_program_publication import CheckProgramSetup
from support.coding_cli import write_codex_cli
from support.coding_resources import saved_coding_candidate
from support.delivery_composition import delivery_graph
from support.engineering_api import engineering_api, policies
from support.engineering_programs import engineering_configuration
from support.feature_api import feature_workflow_access
from support.http_programs import publish_program
from support.python_checks import ADDITION, python_verifier_definition
from support.review_api import pending_review
from support.review_programs import review_body

from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramDefinition
from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.check_runs import CheckRun
from lumora.services.verification.domain.models import CheckRequirement
from plugins.adlc.programs.program import EngineeringInput, EngineeringResult
from plugins.codex.config import CodexConfig
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS as CHECKS


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "decisions,reason",
    [
        (("approve",), "satisfied"),
        (("reject", "approve"), "satisfied"),
        (("reject", "reject"), "limit_reached"),
    ],
)
async def test_delivery_repeat_codes_checks_and_reviews_exact_candidates(
    application,
    mongo_database,
    redis_uri,
    tmp_path,
    profile,
    decisions,
    reason,
):
    owner = application.owner
    for spec in (*REVIEWS, *CHECKS):
        application.elements.register_spec_class(spec)
    executable = write_codex_cli(tmp_path)
    requirements = (
        CheckRequirement(
            check="tests@1", verifiers=frozenset({"program-ci"}), requires_reports=True
        ),
    )
    policy, runner = policies(owner)
    policy = policy.model_copy(update={"requirements": requirements})
    runner = runner.model_copy(update={"verifier": "program-ci"})
    setup = CheckProgramSetup(
        python_verifier_definition(Identity.user("trusted-verifier"), profile),
        runner,
        input_artifact_max_bytes=65_536,
    )
    async with engineering_api(
        owner,
        mongo_database.name,
        redis_uri,
        tmp_path,
        application_modules=(
            "plugins.adlc.programs.coding",
            "plugins.testing.programs.python_check",
            "support.typed_programs",
        ),
        element_modules=("plugins.codex.specification", "plugins.testing.specification"),
        library=True,
        factory="lumora.bootstrap.asgi:create_app",
        verification_policies={"engineering@1": policy},
        check_programs={"python@1": setup},
        environment={
            "PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", ""),
            "LUMORA_PYTHON_CHECK_EXECUTION_ENABLED": "true",
            "LUMORA_PYTHON_CHECK_DIRECTORY": str(tmp_path / "checks"),
        },
    ) as api:
        coding = await saved_coding_candidate(
            api.http,
            api.human,
            profile=profile,
            config=CodexConfig(
                model="engineering-fixture", api_key=SecretStr("private-test-token")
            ),
        )
        worker = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="coder",
                name="Coding candidate",
                owner=owner,
                implementation=CustomCoordinatorDefinition(
                    implementation="coding_file_candidate",
                    version="1",
                    config=coding.model_dump(mode="json"),
                ),
            ),
            headers=api.human,
        )
        config = engineering_configuration(
            application.elements,
            profile=profile,
            verification_policy="engineering@1",
            runners=("python@1",),
            requirements=requirements,
            max_polls=400,
            poll_interval_seconds=0.1,
        )
        engineering = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="attempt",
                name="Engineering attempt",
                owner=owner,
                input_schema=EngineeringInput.model_json_schema(),
                output_schema=EngineeringResult.model_json_schema(),
                implementation=CustomCoordinatorDefinition(
                    implementation="engineering",
                    version="4",
                    config=config.model_dump(mode="json"),
                    children={
                        "implementation": worker,
                        "repair": worker,
                        "reviewer": review_body(application.elements, profile),
                    },
                ),
            ),
            headers=api.human,
        )
        delivery = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="delivery",
                name="Delivery",
                owner=owner,
                implementation=delivery_graph(engineering, iterations=2),
            ),
            headers=api.human,
        )
        root = uuid4().hex
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": root,
                "program": delivery.model_dump(mode="json"),
                "inputs": {"state": {"task": {"prompt": "Implement add(a, b) in answer.py"}}},
                "workflow_access": [
                    grant.model_dump(mode="json")
                    for grant in feature_workflow_access(ttl_seconds=60, renewable_for_seconds=180)
                ],
            },
        )
        assert started.status_code == 202, started.text
        reviews = []
        for index, decision in enumerate(decisions):
            review = await pending_review(api.http, root, api.human, api.reviewer, timeout=90)
            assert review.review_id not in {item.review_id for item in reviews}
            reviews.append(review)
            candidate = review.specification.subject["candidate"]
            assert candidate["identity"]["sha256"] == hashlib.sha256(ADDITION).hexdigest()
            response = await api.http.post(
                f"/api/reviews/{review.review_id}/responses",
                headers=api.reviewer,
                json={
                    "key": f"decision-{index}",
                    "expected_revision": review.revision,
                    "decision": decision,
                    "data": {"feedback": decision},
                },
            )
            assert response.status_code == 200, response.text
        completed = await api.http.get(
            f"/api/executions/{root}/result", headers=api.human, timeout=90
        )
        assert completed.status_code == 200, completed.text
        record = completed.json()
        assert record["phase"] == "completed", record
        result = record["result"]
        assert result["reason"] == reason and result["iterations"] == len(decisions)
        assert result["last"]["done"] is (reason == "satisfied")
        final = result["last"]["result"]
        assert (
            final["attempts"] == 2
            and final["review"]["review"]["review_id"] == reviews[-1].review_id
        )
        children = (
            await api.http.get(f"/api/executions/{root}/children", headers=api.human)
        ).json()
        assert len(children) == 1 and children[0]["body_path"] == ["improve"]
        iterations = (
            await api.http.get(
                f"/api/executions/{children[0]['execution_id']}/children", headers=api.human
            )
        ).json()
        assert len(iterations) == len(decisions)
        assert len({item["execution_id"] for item in iterations}) == len(decisions)
        assert {item["inputs"]["task"]["prompt"] for item in iterations} == {
            "Implement add(a, b) in answer.py"
        }
        checks = [
            CheckRun.model_validate_json(row["data"])
            async for row in mongo_database.verification_check_runs.find({})
        ]
        checks = [check for check in checks if check.plan.root_execution_id == root]
        assert len(checks) == 2 * len(decisions)
        assert sum(check.observation.verdict == "passed" for check in checks) == len(decisions)
        assert sum(check.observation.verdict == "failed" for check in checks) == len(decisions)
        await asyncio.to_thread(shutil.rmtree, api.workspace)
        downloaded = await api.http.get(
            "/api/artifacts/" + final["candidate"]["identity"]["artifact_id"] + "/content",
            headers=api.human,
        )
        assert downloaded.status_code == 200 and downloaded.content == ADDITION
