"""Graph -> registered operations -> code child -> native API -> durable check peer."""

import asyncio

import pytest
from support.check_api import check_api_settings
from support.check_runs import source_request
from support.github_checks import report_archive
from support.http_programs import publish_program
from support.scenarios import publish
from support.verification_api import verification_api
from support.verification_programs import check_graph, check_wait_definition

from flareward.executions.domain.models import ExecutionPhase, ExecutionRecord
from flareward.executions.models import StartExecution
from flareward.services.verification.domain.check_runs import CheckRun
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS
from plugins.verification.programs.waiting import APPLICATION_PROGRAMS


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("reports_enabled", [False, True])
async def test_registered_workflow_dispatches_once_and_records_exact_check_evidence(
    application,
    mongo_database,
    redis_uri,
    tmp_path,
    profile,
    reports_enabled,
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)
    waiter = await publish(
        application, "await-ci", check_wait_definition(application.elements, profile)
    )
    workflow = await publish(application, "verified-change", check_graph(waiter.reference, profile))
    settings = check_api_settings(
        application.owner,
        mongo_database.name,
        redis_uri,
        artifact_directory=tmp_path / "reports" if reports_enabled else None,
    )
    config = settings.github_checks["github@1"]
    async with verification_api(
        application.owner,
        mongo_database,
        redis_uri,
        tmp_path,
        settings=settings,
        factory="support.check_api:create_app",
        policy="source@1",
        actions=("create", "read", "run_check"),
    ) as api:
        assert (
            await publish_program(api.http, waiter.definition, headers=api.human)
            == waiter.reference
        )
        reference = await publish_program(api.http, workflow.definition, headers=api.human)
        request = source_request()
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json=StartExecution(
                program=reference,
                execution_id=api.root,
                inputs={
                    "subject": request.subject.model_dump(mode="json"),
                    "policy": request.policy,
                },
            ).model_dump(mode="json"),
        )
        assert started.status_code == 202, started.text
        record = ExecutionRecord.model_validate(started.json())
        async with asyncio.timeout(30):
            document = None
            while document is None:
                document = await mongo_database.verification_check_runs.find_one()
                if document is None:
                    await asyncio.sleep(0.02)
            check = CheckRun.model_validate_json(document["data"])
            assert (
                await api.http.get(
                    "/api/verification-checks/" + check.intent_id, headers=api.client
                )
            ).status_code == 200
            denied = await api.http.post(
                f"/api/verification-checks/{check.intent_id}/resolve",
                headers=api.client,
                json={
                    "key": "workflow-cannot-resolve",
                    "expected_revision": check.revision,
                    "external_id": "github-actions:example/product:1001:1",
                    "reason": "Workflow identity is not human review authority",
                },
            )
            assert denied.status_code == 403
            refresh_path = f"POST /api/verification-checks/{check.intent_id}/refresh "
            while refresh_path not in api.log.read_text():
                await asyncio.sleep(0.02)
            await mongo_database.fixture_github_runs.update_one(
                {"_id": 1001}, {"$set": {"run.status": "completed", "run.conclusion": "success"}}
            )
            observed = await api.http.get(
                f"/api/executions/{record.execution_id}/result", headers=api.human
            )
            assert observed.status_code == 200, observed.text
            result = ExecutionRecord.model_validate(observed.json())
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        output = result.result["result"]
        assert output["reason"] == "resolved" and output["polls"] >= 2
        assert output["check"]["evidence_recorded"] is True
        plan = output["check"]["plan"]
        assert (
            await api.http.get("/api/verifications/" + plan["plan_id"], headers=api.client)
        ).status_code == 401
        view = await api.http.get("/api/verifications/" + plan["plan_id"], headers=api.human)
        assert view.status_code == 200, view.text
        assert view.json()["outcome"] == "accepted"
        assert (
            view.json()["state"]["evidence"][0]["subject_fingerprint"]
            == request.subject.fingerprint
        )
        reports = view.json()["state"]["evidence"][0]["reports"]
        assert bool(reports) == reports_enabled
        if reports_enabled:
            assert reports == output["check"]["reports"]
            content_path = "/api/artifacts/" + reports[0]["content"]["artifact_id"] + "/content"
            assert (await api.http.get(content_path, headers=api.client)).status_code == 401
            content = await api.http.get(content_path, headers=api.human)
            assert content.status_code == 200 and content.content == report_archive()
        assert await mongo_database.fixture_github_runs.count_documents({}) == 1
        children = [
            ExecutionRecord.model_validate(child)
            for child in (
                await api.http.get(f"/api/executions/{api.root}/children", headers=api.human)
            ).json()
        ]
        assert len(children) == 1 and children[0].program == waiter.reference
        assert (
            config.token.get_secret_value()
            not in workflow.model_dump_json()
            + waiter.model_dump_json()
            + str(result.result)
            + api.log.read_text()
        )
