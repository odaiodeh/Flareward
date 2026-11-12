"""Graph and code composition uses scoped native verification, not evidence authority."""

import asyncio
import json

import pytest
from support.http_programs import publish_program
from support.scenarios import publish, run
from support.verification import evidence_request, verification_request
from support.verification_api import verification_api
from support.verification_programs import (
    verification_graph,
    verification_resources,
    verification_wait_definition,
)

from lumora.executions.domain.models import ExecutionPhase, ExecutionRecord, FailureKind
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.executions.models import StartExecution
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import GraphDefinition, OperationStep
from lumora.resources.domain.bundles import ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS
from plugins.verification.programs.waiting import COORDINATORS


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("cancel_before_wait", [False, True])
@pytest.mark.parametrize("managed_delivery", [False, True])
async def test_graph_and_reusable_waiter_use_root_scoped_access_without_evidence_authority(
    application,
    mongo_database,
    redis_uri,
    tmp_path,
    profile,
    cancel_before_wait,
    managed_delivery,
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    for registration in COORDINATORS:
        application.applications.register(registration)
    waiter = await publish(
        application, "await-checks", verification_wait_definition(application.elements, profile)
    )
    workflow = await publish(
        application,
        "verified-workflow",
        verification_graph(waiter.reference, profile, cancel_before_wait=cancel_before_wait),
    )
    async with verification_api(
        application.owner, mongo_database, redis_uri, tmp_path, managed_delivery=managed_delivery
    ) as api:
        assert (
            await publish_program(api.http, waiter.definition, headers=api.human)
            == waiter.reference
        )
        reference = await publish_program(api.http, workflow.definition, headers=api.human)
        assert api.grant.issued_by.owns(application.owner)
        assert (
            await api.http.post(
                "/api/verification-access",
                headers=api.client,
                json={"scope": api.grant.scope.model_dump(mode="json")},
            )
        ).status_code == 401
        assert (
            await api.http.get("/api/catalog/execution-profiles", headers=api.client)
        ).status_code == 401
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json=StartExecution(
                program=reference,
                execution_id=api.root,
                inputs={
                    "subject": verification_request().subject.model_dump(mode="json"),
                    "policy": "release@1",
                },
            ).model_dump(mode="json"),
        )
        assert started.status_code == 202, started.text
        record = ExecutionRecord.model_validate(started.json())
        async with asyncio.timeout(30):
            plan = await api.inspected_plan()
            assert (
                await api.http.post(
                    "/api/verification-evidence",
                    headers={**api.client, "X-Verification-Authority": "ci"},
                    json=evidence_request(plan).model_dump(mode="json"),
                )
            ).status_code == 401
            if not cancel_before_wait:
                await api.attest(plan)
            observed = await api.http.get(
                f"/api/executions/{record.execution_id}/result", headers=api.human
            )
            assert observed.status_code == 200, observed.text
            result = ExecutionRecord.model_validate(observed.json())
        assert result.phase == ExecutionPhase.COMPLETED, result.failure
        output = result.result["result"]
        assert output["reason"] == "resolved"
        assert (output["polls"] == 1) if cancel_before_wait else (output["polls"] >= 2)
        assert output["verification"]["outcome"] == (
            "cancelled" if cancel_before_wait else "accepted"
        )
        assert output["verification"]["state"]["plan"]["plan_id"] == plan.plan_id
        children = [
            ExecutionRecord.model_validate(child)
            for child in (
                await api.http.get(f"/api/executions/{api.root}/children", headers=api.human)
            ).json()
        ]
        assert len(children) == 1 and children[0].program == waiter.reference
        listed = await api.http.get("/api/verification-access", headers=api.human)
        credential = api.credential.get_secret_value()
        assert credential not in listed.text
        assert (
            await api.http.delete(
                "/api/verification-access/" + api.grant.grant_id, headers=api.human
            )
        ).status_code == 204
        assert (
            await api.http.get("/api/verification-access/self", headers=api.client)
        ).status_code == 401
        portable = json.dumps(result.result) + workflow.model_dump_json() + waiter.model_dump_json()
        assert all(
            secret not in portable and secret not in api.log.read_text()
            for secret in (
                credential,
                *(value.get_secret_value() for value in api.issuers.values()),
            )
        )
        if managed_delivery:
            async with asyncio.timeout(10):
                while True:
                    material = await mongo_database.workflow_credential_material.find_one({})
                    if material["retired"] and not material["cleanup_pending"]:
                        break
                    await asyncio.sleep(0.05)
            assert "credential" not in material
            assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))
            assert not list(api.directory.iterdir())


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_unavailable_verification_service_is_retryable_infrastructure_without_private_values(
    platform, application, mongo_database, redis_uri, tmp_path, monkeypatch, profile
):
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    definition = GraphDefinition(
        resources=verification_resources(),
        steps=(
            OperationStep(
                uid="request",
                element=ResourceKey(category=ResourceCategory.OPERATION, rid="request"),
                execution=ExecutionSelection(profile=profile),
                inputs={
                    "subject": PathBinding(path=("values", "subject")),
                    "policy": PathBinding(path=("values", "policy")),
                },
            ),
        ),
        entry="request",
        exit="request",
        inputs={"values": PathBinding(path=())},
    )
    revision = await publish(platform, "unavailable-checks", definition)
    async with verification_api(platform.owner, mongo_database, redis_uri, tmp_path) as api:
        for key, value in api.operator_environment.items():
            monkeypatch.setenv(key, value)
    record = await run(
        platform,
        revision,
        {
            "subject": verification_request().subject.model_dump(mode="json"),
            "policy": "release@1",
        },
        execution_id=api.root,
    )
    assert record.phase == ExecutionPhase.FAILED
    assert record.failure.kind == FailureKind.INFRASTRUCTURE and record.failure.retryable
    assert api.credential.get_secret_value() not in record.failure.message
    assert str(tmp_path) not in record.failure.message
