"""One immutable Engineering publication accepts file or retained Git deliverables."""

import asyncio
import hashlib
import json
import os
import shutil
from uuid import uuid4

import pytest
from pydantic import SecretStr
from support.check_program_publication import CheckProgramSetup
from support.coding_cli import write_codex_cli
from support.coding_resources import CodingResourceLibrary, saved_coding_candidate
from support.completion_contracts import FileCandidate, GitCandidate
from support.engineering_api import engineering_api, policies
from support.engineering_programs import engineering_configuration
from support.feature_api import feature_workflow_access
from support.feature_design import design_definition
from support.git_resources import git_resources
from support.http_programs import publish_program
from support.python_checks import ADDITION, addition_cases, python_verifier_definition
from support.repositories import LocalRepository
from support.review_api import pending_review
from support.review_programs import review_body

from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    OperationStep,
    ProgramBody,
    ProgramDefinition,
)
from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.check_runs import CheckRun
from lumora.services.verification.domain.models import CheckRequirement
from plugins.adlc.programs.design import DesignResult, FeatureRequest
from plugins.adlc.programs.feature import CodingFeatureInput, CodingFeatureResult
from plugins.adlc.programs.program import (
    EngineeringCompletion,
    EngineeringConfig,
    EngineeringInput,
    EngineeringResult,
)
from plugins.adlc.programs.review import EngineeringReviewSubject
from plugins.adlc_git.programs.coding import CodingGitConfig
from plugins.codex.config import CodexConfig
from plugins.git.domain.repositories import GitFile, GitFileContent
from plugins.git.elements.config import GitBinding
from plugins.git.elements.specification import ELEMENT_SPECIFICATIONS as GIT
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from plugins.testing.programs.git_check import GitPythonCheckConfig
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS as CHECKS


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_same_engineering_revision_selects_real_file_or_git_work(
    application, mongo_database, redis_uri, tmp_path, profile
):
    owner, verifier = application.owner, Identity.user("trusted-verifier")
    retained = tmp_path / "retained.git"
    retained.mkdir()
    repository = LocalRepository(retained)
    await repository.git("init", "--quiet", "--bare", "--initial-branch=main")
    executable = write_codex_cli(tmp_path, git_repository=retained)
    for spec in (*GIT, *REVIEWS, *CHECKS):
        application.elements.register_spec_class(spec)
    resources = git_resources()
    resolver = ElementBundleResolver(application.elements)
    reader = resolver.resolve(resources[2].key, resources)
    requirements = (
        CheckRequirement(
            check="tests@1", verifiers=frozenset({"program-ci"}), requires_reports=True
        ),
    )
    verification_policies = {}
    check_programs = {}
    for name, kind in (("files", "blob-artifact@1"), ("git", "git-revision@1")):
        policy, check_policy = policies(owner)
        verification_policies[name + "@1"] = policy.model_copy(
            update={"subject_kind": kind, "requirements": requirements}
        )
        check_policy = check_policy.model_copy(
            update={
                "policies": frozenset({name + "@1"}),
                "subject_kind": kind,
                "verifier": "program-ci",
            }
        )
        if name == "files":
            definition = python_verifier_definition(verifier, profile).model_copy(
                update={"program_id": "trusted-files"}
            )
        else:
            definition = ProgramDefinition(
                program_id="trusted-git",
                name="Trusted Git checks",
                owner=verifier,
                implementation=CustomCoordinatorDefinition(
                    implementation="git_python_function_check",
                    version="1",
                    config=GitPythonCheckConfig(
                        reader=reader,
                        path="answer.py",
                        source_execution=ExecutionSelection(profile=profile),
                        comparison=addition_cases().model_copy(
                            update={"execution": ExecutionSelection(profile=profile)}
                        ),
                    ).model_dump(mode="json"),
                ),
            )
        check_programs[name + "-check@1"] = CheckProgramSetup(
            definition, check_policy, input_artifact_max_bytes=65_536 if name == "files" else None
        )
    environment = {
        "PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", ""),
        "LUMORA_PYTHON_CHECK_EXECUTION_ENABLED": "true",
        "LUMORA_PYTHON_CHECK_DIRECTORY": str(tmp_path / "check-workspaces"),
        "LUMORA_GIT_REPOSITORIES": json.dumps(
            {
                "product": GitBinding(location=str(retained), owners=(owner, verifier)).model_dump(
                    mode="json"
                )
            }
        ),
    }
    async with engineering_api(
        owner,
        mongo_database.name,
        redis_uri,
        tmp_path,
        application_modules=(
            "plugins.adlc.programs.coding",
            "plugins.adlc_git.programs.coding",
            "plugins.adlc.programs.design",
            "plugins.adlc.programs.feature",
            "plugins.testing.programs.python_check",
            "plugins.testing.programs.git_check",
            "support.feature_design",
        ),
        element_modules=(
            "plugins.codex.specification",
            "plugins.git.elements.specification",
            "plugins.testing.specification",
        ),
        library=True,
        factory="lumora.bootstrap.asgi:create_app",
        environment=environment,
        verification_policies=verification_policies,
        check_programs=check_programs,
    ) as api:
        file_config = await saved_coding_candidate(
            api.http,
            api.human,
            profile=profile,
            config=CodexConfig(
                model="engineering-fixture", api_key=SecretStr("private-test-token")
            ),
        )
        library = CodingResourceLibrary(api.http, api.human)
        source = await library.create("providers", "git_repository", {"repository": "product"})
        resolve = await library.create(
            "operations",
            "resolve_git_revision",
            {"source": "$ref:" + source["rid"]},
            execution_profile=profile,
        )
        git_config = CodingGitConfig(
            coding=await library.coding(
                CodexConfig(model="git-fixture", api_key=SecretStr("private-test-token")),
                profile,
                name="Git coding agent",
            ),
            loader=file_config.loader,
            resolver=await library.capture(resolve),
            repository="product",
            execution=ExecutionSelection(profile=profile),
            artifact_execution=ExecutionSelection(profile=profile),
            repository_execution=ExecutionSelection(profile=profile),
        )
        children = {}
        completions = []
        baseline = engineering_configuration(application.elements).completions[0]
        for name, config, implementation, schema in (
            ("files", file_config, "coding_file_candidate", FileCandidate),
            ("git", git_config, "coding_git_candidate", GitCandidate),
        ):
            child = await publish_program(
                api.http,
                ProgramDefinition(
                    program_id=name + "-worker",
                    name=name + " worker",
                    owner=owner,
                    implementation=CustomCoordinatorDefinition(
                        implementation=implementation,
                        version="1",
                        config=config.model_dump(mode="json"),
                    ),
                ),
                headers=api.human,
            )
            children[name] = children[name + "-repair"] = child
            completions.append(
                EngineeringCompletion.model_validate(
                    {
                        **baseline.model_dump(),
                        "name": name,
                        "candidate_schema": schema.model_json_schema(),
                        "implementation": name,
                        "repair": name + "-repair",
                        "verification_policy": name + "@1",
                        "requirements": requirements,
                        "runners": (name + "-check@1",),
                    }
                )
            )
        config = EngineeringConfig.model_validate(
            {
                **engineering_configuration(
                    application.elements, profile=profile, max_polls=400, poll_interval_seconds=0.1
                ).model_dump(),
                "default_completion": "files",
                "completions": completions,
            }
        )
        reference = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="completion-choices",
                name="Engineering choices",
                owner=owner,
                implementation=CustomCoordinatorDefinition(
                    implementation="engineering",
                    version="4",
                    config=config.model_dump(mode="json"),
                    children={**children, "reviewer": review_body(application.elements, profile)},
                ),
                input_schema=EngineeringInput.model_json_schema(),
                output_schema=EngineeringResult.model_json_schema(),
            ),
            headers=api.human,
        )
        revision_path = "/api/programs/" + reference.program_id + "/revisions/1"
        frozen = (await api.http.get(revision_path, headers=api.human)).json()
        feature = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="feature-choices",
                name="Design and select completion",
                owner=owner,
                implementation=CustomCoordinatorDefinition(
                    implementation="coding_feature",
                    version="1",
                    children={
                        "design": ProgramBody(
                            implementation=design_definition(application.elements, profile),
                            input_schema=FeatureRequest.model_json_schema(),
                            output_schema=DesignResult.model_json_schema(),
                        ),
                        "engineering": reference,
                    },
                ),
                input_schema=CodingFeatureInput.model_json_schema(),
                output_schema=CodingFeatureResult.model_json_schema(),
            ),
            headers=api.human,
        )
        results = {}
        reports = []
        for choice in ("files", "git"):
            root = uuid4().hex
            access = [
                value.model_dump(mode="json")
                for value in feature_workflow_access(ttl_seconds=60, renewable_for_seconds=180)
            ]
            for grant in access:
                if grant["purpose"] == "verification@1":
                    grant["scope"]["policies"] = [choice + "@1"]
            inputs = {"task": {"prompt": "Implement add(a, b) in answer.py"}}
            if choice == "git":
                inputs = {
                    "prompt": "Implement add(a, b) in answer.py",
                    "acceptance_criteria": ["Handles positive and negative numbers"],
                    "completion": choice,
                }
            started = await api.http.post(
                "/api/executions",
                headers=api.human,
                json={
                    "execution_id": root,
                    "program": (feature if choice == "git" else reference).model_dump(mode="json"),
                    "inputs": inputs,
                    "workflow_access": access,
                },
            )
            assert started.status_code == 202, started.text
            if choice == "git":
                design = await pending_review(
                    api.http, root, api.human, api.reviewer, design_number=1
                )
                before_design_approval = [
                    CheckRun.model_validate_json(row["data"])
                    async for row in mongo_database.verification_check_runs.find({})
                ]
                assert all(check.plan.root_execution_id != root for check in before_design_approval)
                children = (
                    await api.http.get("/api/executions/" + root + "/children", headers=api.human)
                ).json()
                assert not any(
                    child["program"] == reference.model_dump(mode="json") for child in children
                )
                accepted = await api.http.post(
                    "/api/reviews/" + design.review_id + "/responses",
                    headers=api.reviewer,
                    json={
                        "key": "approve-design",
                        "expected_revision": design.revision,
                        "decision": "approve",
                        "data": {"feedback": "Implement and independently verify the proposal"},
                    },
                )
                assert accepted.status_code == 200, accepted.text
            review = await pending_review(api.http, root, api.human, api.reviewer, timeout=90)
            reviewed = EngineeringReviewSubject.model_validate(review.specification.subject)
            assert reviewed.completion == choice and reviewed.verification.outcome == "accepted"
            assert reviewed.candidate.kind == (
                "blob-artifact@1" if choice == "files" else "git-revision@1"
            )
            checks = [
                CheckRun.model_validate_json(row["data"])
                async for row in mongo_database.verification_check_runs.find({})
            ]
            checks = [check for check in checks if check.plan.root_execution_id == root]
            assert len(checks) == 2 and {check.observation.verdict for check in checks} == {
                "failed",
                "passed",
            }
            for check in checks:
                assert (
                    await api.http.get(
                        "/api/executions/" + check.observation.external_id, headers=api.human
                    )
                ).status_code == 403
                observed = (
                    await api.http.get(
                        "/api/executions/" + check.observation.external_id,
                        headers=api.verifiers[choice + "-check@1"],
                    )
                ).json()
                assert observed["program"] == api.check_bindings[
                    choice + "-check@1"
                ].program.model_dump(mode="json")
            report = reviewed.verification.state.evidence[0].reports[0].content
            content = (
                await api.http.get(
                    "/api/artifacts/" + report.artifact_id + "/content", headers=api.human
                )
            ).content
            assert hashlib.sha256(content).hexdigest() == report.sha256
            assert json.loads(content)["details"] == {"cases": 3, "failures": []}
            reports.append(report)
            accepted = await api.http.post(
                "/api/reviews/" + review.review_id + "/responses",
                headers=api.reviewer,
                json={
                    "key": "approve",
                    "expected_revision": review.revision,
                    "decision": "approve",
                    "data": {"feedback": "Accept the exact checked candidate"},
                },
            )
            assert accepted.status_code == 200, accepted.text
            observed = (
                await api.http.get("/api/executions/" + root + "/result", headers=api.human)
            ).json()
            assert observed["phase"] == "completed", observed
            if choice == "git":
                composed = CodingFeatureResult.model_validate(observed["result"])
                assert composed.outcome == "verified" and composed.design.outcome == "approved"
                result = composed.engineering
                children = (
                    await api.http.get("/api/executions/" + root + "/children", headers=api.human)
                ).json()
                assert any(
                    child["program"] == reference.model_dump(mode="json") for child in children
                )
            else:
                result = EngineeringResult.model_validate(observed["result"])
            assert (
                result.outcome == "verified"
                and result.completion == choice
                and result.attempts == 2
            )
            results[choice] = result
            assert (await api.http.get(revision_path, headers=api.human)).json() == frozen
        await asyncio.to_thread(shutil.rmtree, api.workspace)
        artifact = results["files"].candidate.identity
        assert (
            await api.http.get(
                "/api/artifacts/" + artifact["artifact_id"] + "/content", headers=api.human
            )
        ).content == ADDITION
        retained_reader = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="retained-source",
                name="Read retained source",
                owner=owner,
                implementation=GraphDefinition(
                    resources=resources,
                    steps=(
                        OperationStep(
                            uid="read",
                            element=resources[2].key,
                            execution=ExecutionSelection(profile=profile),
                            inputs=PathBinding(path=("input",)),
                        ),
                    ),
                    entry="read",
                    exit="read",
                    outputs=PathBinding(path=("results", "read")),
                ),
                input_schema=GitFile.model_json_schema(),
                output_schema=GitFileContent.model_json_schema(),
            ),
            headers=api.human,
        )
        read_root = uuid4().hex
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": read_root,
                "program": retained_reader.model_dump(mode="json"),
                "inputs": {"revision": results["git"].candidate.identity, "path": "answer.py"},
            },
        )
        assert started.status_code == 202, started.text
        read = (
            await api.http.get("/api/executions/" + read_root + "/result", headers=api.human)
        ).json()
        assert read["phase"] == "completed", read
        assert GitFileContent.model_validate(read["result"]).content.decoded() == ADDITION
        for report in reports:
            content = (
                await api.http.get(
                    "/api/artifacts/" + report.artifact_id + "/content", headers=api.human
                )
            ).content
            assert hashlib.sha256(content).hexdigest() == report.sha256
        async with asyncio.timeout(20):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert await mongo_database.workflow_credential_material.count_documents({}) == 6
        assert (
            await mongo_database.workflow_credential_material.count_documents(
                {"credential": {"$exists": True}}
            )
            == 0
        )
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
        public = json.dumps(
            {choice: value.model_dump(mode="json") for choice, value in results.items()}
        )
        assert "private-test-token" not in public and str(retained) not in public
        (tmp_path / "accepted-completions.json").write_text(
            json.dumps(
                {
                    "program": reference.model_dump(mode="json"),
                    "content_digest": frozen["content_digest"],
                    "git_composition": {
                        "program": feature.model_dump(mode="json"),
                        "engineering": reference.model_dump(mode="json"),
                        "design_approved": True,
                    },
                    "results": {
                        choice: value.model_dump(mode="json") for choice, value in results.items()
                    },
                    "source_survived_compute_removal": True,
                    "retired_capabilities": 6,
                },
                indent=2,
            )
            + "\n"
        )
