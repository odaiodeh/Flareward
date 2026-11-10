"""Production GitHub adapter contract and real durable native API reconstruction."""

import asyncio
import json
from datetime import UTC, datetime

import httpx
import pytest
from fastapi import HTTPException
from support.check_runs import MemoryCheckRunRepository, source_policy, source_request
from support.execution_access import ExecutionAuthority
from support.github_checks import GitHubProtocol, github_configuration
from support.verification import MemoryVerificationRepository, VerificationClock

from lumora.api.app import create_app
from lumora.services.identity.domain import Identity
from lumora.services.verification.access import VerificationAccessService
from lumora.services.verification.access_models import (
    VerificationAccessRequest,
    VerificationAccessScope,
    VerificationAction,
    VerificationActor,
)
from lumora.services.verification.adapters.mongo.check_runs import MongoCheckRunRepository
from lumora.services.verification.adapters.mongo.verification_access import (
    MongoVerificationAccessRepository,
)
from lumora.services.verification.adapters.mongo.verification_repository import (
    MongoVerificationRepository,
)
from lumora.services.verification.check_ports import CheckProviderUnavailable, StartCheckRun
from lumora.services.verification.check_service import CheckRunService, RegisteredCheckRunner
from lumora.services.verification.domain.check_runs import CheckRunStatus
from lumora.services.verification.domain.models import VerificationOutcome
from lumora.services.verification.service import VerificationService
from plugins.github_actions.github import GitHubActionsCheckRunner


@pytest.mark.parametrize("lost_acknowledgement", [False, True])
async def test_native_api_reconstructs_dispatch_and_attests_without_repeating_post(
    platform, mongo_database, lost_acknowledgement
):
    owner, clock = Identity.user("owner"), VerificationClock(datetime.now(UTC))
    policies = {"source@1": source_policy(owner)}
    wire, config = (
        GitHubProtocol(lose_acknowledgement=lost_acknowledgement),
        github_configuration(owner),
    )
    access_repository = MongoVerificationAccessRepository(mongo_database)
    await access_repository.initialize()
    access = VerificationAccessService(
        access_repository, policies, clock=clock, execution_authority=ExecutionAuthority()
    )
    issued = await access.issue(
        VerificationAccessRequest(
            scope=VerificationAccessScope(
                root_execution_id="root",
                policies=frozenset({"source@1"}),
                actions=frozenset(
                    {
                        VerificationAction.CREATE,
                        VerificationAction.READ,
                        VerificationAction.RUN_CHECK,
                    }
                ),
            )
        ),
        owner,
        owner,
    )
    headers = {"Authorization": "Bearer " + issued.credential.get_secret_value()}

    async def human(request):
        if request.headers.get("X-Human") != "owner":
            raise HTTPException(401, "Human session required")
        return owner

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(wire), follow_redirects=False
    ) as provider:
        driver = GitHubActionsCheckRunner(config, provider)

        def native_app():
            verification = VerificationService(
                MongoVerificationRepository(mongo_database), policies, clock=clock
            )
            checks = CheckRunService(
                MongoCheckRunRepository(mongo_database),
                verification,
                {"github@1": RegisteredCheckRunner(config.policy, driver)},
                clock=clock,
            )
            return create_app(
                platform.programs,
                platform.executions,
                human,
                verifications=verification,
                verification_access=access,
                check_runs=checks,
            )

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(native_app()), base_url="http://native"
        ) as http:
            response = await http.post(
                "/api/verifications", headers=headers, json=source_request().model_dump(mode="json")
            )
            assert response.status_code == 200, response.text
            plan_id = response.json()["state"]["plan"]["plan_id"]
            request = {"plan_id": plan_id, "runner": "github@1"}
            responses = await asyncio.gather(
                *(
                    http.post("/api/verification-checks", headers=headers, json=request)
                    for _ in range(10)
                )
            )
            assert {result.status_code for result in responses} == {200}
            assert wire.submissions == 1
            intent_id = responses[0].json()["intent_id"]
            assert all(result.headers["cache-control"] == "no-store" for result in responses)
        wire.complete()
        # Fresh service/repository/router instances recover durable intent and evidence.
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(native_app()), base_url="http://native"
        ) as http:
            refresh = await http.post(
                f"/api/verification-checks/{intent_id}/refresh", headers=headers
            )
            assert refresh.status_code == 200, refresh.text
            assert refresh.json()["evidence_recorded"] is True
            view = await http.get("/api/verifications/" + plan_id, headers=headers)
            assert view.json()["outcome"] == "accepted"
            receipt = view.json()["state"]["evidence"][0]
            assert receipt["run_id"] == "github-actions:example/product:1001:1"
            assert (
                await http.post("/api/verification-checks", headers=headers, json=request)
            ).json() == refresh.json()
            assert wire.submissions == 1
            stored = await mongo_database.verification_check_runs.find_one({"_id": intent_id})
            assert config.token.get_secret_value() not in json.dumps(stored)
            assert issued.credential.get_secret_value() not in json.dumps(stored)
            assert receipt["subject_fingerprint"] == source_request().subject.fingerprint
            await access.revoke(issued.grant.grant_id, owner)
            assert (
                await http.post(f"/api/verification-checks/{intent_id}/refresh", headers=headers)
            ).status_code == 401


@pytest.mark.parametrize(
    "field,value",
    [
        ("head_sha", "d" * 40),
        ("run_attempt", 2),
        ("workflow_id", 99),
        ("event", "push"),
        ("display_title", "wrong-intent"),
        ("repository", {"full_name": "attacker/product"}),
    ],
)
async def test_provider_run_with_wrong_provenance_cannot_attest(field, value):
    owner, clock = Identity.user("owner"), VerificationClock()
    actor = VerificationActor(owner)
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": source_policy(owner)}, clock=clock
    )
    plan = (await verification.start(source_request(), actor)).state.plan
    wire, config = GitHubProtocol(), github_configuration(owner)
    async with httpx.AsyncClient(transport=httpx.MockTransport(wire)) as provider:
        driver = GitHubActionsCheckRunner(config, provider)
        checks = CheckRunService(
            MemoryCheckRunRepository(),
            verification,
            {"github@1": RegisteredCheckRunner(config.policy, driver)},
            clock=clock,
        )
        run = await checks.start(StartCheckRun(plan_id=plan.plan_id, runner="github@1"), actor)
        wire.complete()
        wire.runs[0][field] = value
        with pytest.raises(CheckProviderUnavailable):
            await driver.reconcile(run)
        assert not (await checks.refresh(run.intent_id, actor)).evidence_recorded
        assert (
            await verification.inspect(plan.plan_id, actor)
        ).outcome == VerificationOutcome.PENDING


@pytest.mark.parametrize("case", ["absent", "duplicate", "truncated"])
async def test_uncertain_dispatch_search_fails_closed_without_resubmission(case):
    owner, clock = Identity.user("owner"), VerificationClock()
    actor = VerificationActor(owner)
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": source_policy(owner)}, clock=clock
    )
    plan = (await verification.start(source_request(), actor)).state.plan
    wire, config = GitHubProtocol(lose_acknowledgement=True), github_configuration(owner)
    async with httpx.AsyncClient(transport=httpx.MockTransport(wire)) as provider:
        driver = GitHubActionsCheckRunner(config, provider)
        checks = CheckRunService(
            MemoryCheckRunRepository(),
            verification,
            {"github@1": RegisteredCheckRunner(config.policy, driver)},
            clock=clock,
        )
        run = await checks.start(StartCheckRun(plan_id=plan.plan_id, runner="github@1"), actor)
        assert run.status == CheckRunStatus.UNCERTAIN
        if case == "absent":
            wire.runs.clear()
        elif case == "duplicate":
            wire.runs.append({**wire.runs[0], "id": 1002})
        else:
            wire.total_count = 1001
        assert (await checks.refresh(run.intent_id, actor)).status == CheckRunStatus.UNCERTAIN
        assert wire.submissions == 1
        assert (
            await verification.inspect(plan.plan_id, actor)
        ).outcome == VerificationOutcome.PENDING


@pytest.mark.parametrize(
    "status,expected",
    [
        (403, CheckRunStatus.REJECTED),
        (500, CheckRunStatus.UNCERTAIN),
        (204, CheckRunStatus.UNCERTAIN),
    ],
)
async def test_dispatch_refusal_and_ambiguous_responses_never_trigger_a_second_post(
    status, expected
):
    owner, clock = Identity.user("owner"), VerificationClock()
    actor = VerificationActor(owner)
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": source_policy(owner)}, clock=clock
    )
    plan = (await verification.start(source_request(), actor)).state.plan
    wire, config = GitHubProtocol(), github_configuration(owner)
    wire.post_status = status
    async with httpx.AsyncClient(transport=httpx.MockTransport(wire)) as provider:
        driver = GitHubActionsCheckRunner(config, provider)
        checks = CheckRunService(
            MemoryCheckRunRepository(),
            verification,
            {"github@1": RegisteredCheckRunner(config.policy, driver)},
            clock=clock,
        )
        request = StartCheckRun(plan_id=plan.plan_id, runner="github@1")
        run = await checks.start(request, actor)
        assert run.status == expected
        assert (await checks.start(request, actor)).status == expected
        assert wire.submissions == 1
        assert "private provider diagnostic" not in run.model_dump_json()


async def test_reconciliation_has_one_deadline_across_all_provider_pages():
    owner, clock = Identity.user("owner"), VerificationClock()
    actor = VerificationActor(owner)
    verification = VerificationService(
        MemoryVerificationRepository(), {"source@1": source_policy(owner)}, clock=clock
    )
    plan = (await verification.start(source_request(), actor)).state.plan
    wire = GitHubProtocol(lose_acknowledgement=True)
    wire.total_count = 200
    config = github_configuration(owner).model_copy(update={"timeout_seconds": 1})
    calls = []

    async def slow_pages(request):
        if request.method == "GET":
            calls.append(request)
            await asyncio.sleep(0.6)
        return wire(request)

    async with httpx.AsyncClient(transport=httpx.MockTransport(slow_pages)) as provider:
        driver = GitHubActionsCheckRunner(config, provider)
        checks = CheckRunService(
            MemoryCheckRunRepository(),
            verification,
            {"github@1": RegisteredCheckRunner(config.policy, driver)},
            clock=clock,
        )
        run = await checks.start(StartCheckRun(plan_id=plan.plan_id, runner="github@1"), actor)
        with pytest.raises(CheckProviderUnavailable, match="deadline"):
            await driver.reconcile(run)
        assert len(calls) == 2 and wire.submissions == 1
