"""Native verifier evidence, ownership, restart and actual job cancellation."""

import asyncio
import json
import os
import signal
from uuid import uuid4

import pytest
from support.http_programs import publish_program
from support.program_check_api import prepared_verifier
from support.python_checks import ADDITION, SUBTRACTION, addition_cases

from lumora.programs.domain.models import CustomCoordinatorDefinition, ProgramDefinition
from lumora.services.verification.domain.models import VerificationSubject


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize(
    "value,outcome",
    [
        (42, "accepted"),
        (41, "rejected"),
        (ADDITION, "accepted"),
        (SUBTRACTION, "rejected"),
    ],
)
async def test_operator_pinned_program_checks_persist_reports_and_owner_boundaries(
    mongo_database, redis_uri, tmp_path, profile, value, outcome
):
    async with prepared_verifier(mongo_database.name, redis_uri, tmp_path, profile, value) as api:
        async with api.serve("checks") as http:
            check = await api.start_check(http)
            plan_id = check["plan"]["plan_id"]
            intent = check["intent_id"]
            check = await api.settled_check(http, intent)
            execution = check["observation"]["external_id"]
            assert (
                await http.get(f"/api/executions/{execution}", headers=api.human)
            ).status_code == 403
            observed = await http.get(f"/api/executions/{execution}", headers=api.verifier)
            assert observed.status_code == 200, observed.text
            assert observed.json()["program"] == api.reference.model_dump(mode="json")
            assert observed.json()["owner"]["id"] == api.operator.id
            assert observed.json()["workflow_access_approval"] is None
            if isinstance(value, bytes):
                assert observed.json()["inputs"]["artifact"]["reference"] == api.subject.identity
                assert not list((tmp_path / "check-workspaces").iterdir())
            assert (await http.get(f"/api/verifications/{plan_id}", headers=api.human)).json()[
                "outcome"
            ] == outcome
            report = check["reports"][0]["content"]
            content = await http.get(
                f"/api/artifacts/{report['artifact_id']}/content", headers=api.human
            )
            assert content.status_code == 200, content.text
            result = json.loads(content.content)
            subject = VerificationSubject.model_validate(check["plan"]["subject"])
            assert result["subject_fingerprint"] == subject.fingerprint
            assert result["verdict"] == check["observation"]["verdict"]
        async with api.serve("restored") as http:
            response = await http.post(
                f"/api/verification-checks/{intent}/refresh", headers=api.human
            )
            assert response.status_code == 200 and response.json() == check, response.text
            recovered = await http.get(
                f"/api/artifacts/{report['artifact_id']}/content", headers=api.human
            )
            assert recovered.status_code == 200 and recovered.content == content.content


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("cancel", ["plan", "root"])
async def test_plan_or_owning_root_cancellation_closes_actual_checker_and_collects_workspace(
    mongo_database, redis_uri, tmp_path, profile, cancel
):
    marker = tmp_path / "owned-check-pid"
    source = (
        "import os\nfrom pathlib import Path\n"
        f"Path({str(marker)!r}).write_text(str(os.getpid()))\n"
        "while True:\n    pass\n"
    ).encode()
    # Pool executors drain running invocations on cancellation. Keep their owned
    # subprocess bounded; do not pretend a cancel acknowledgement preempts it.
    checker = addition_cases(timeout_seconds=6)
    child = None
    try:
        async with prepared_verifier(
            mongo_database.name, redis_uri, tmp_path, profile, source, checker=checker
        ) as api:
            async with api.serve("cancel") as http:
                headers = api.human
                root = None
                if cancel == "root":
                    reference = await publish_program(
                        http,
                        ProgramDefinition(
                            program_id="owning-workflow",
                            name="Owning workflow",
                            owner=api.owner,
                            implementation=CustomCoordinatorDefinition(
                                implementation="waiting", version="1"
                            ),
                        ),
                        headers=api.human,
                    )
                    root = uuid4().hex
                    response = await http.post(
                        "/api/executions",
                        headers=api.human,
                        json={
                            "program": reference.model_dump(mode="json"),
                            "execution_id": root,
                        },
                    )
                    assert response.status_code == 202, response.text
                    grant = await http.post(
                        "/api/verification-access",
                        headers=api.human,
                        json={
                            "scope": {
                                "root_execution_id": root,
                                "policies": ["value@1"],
                                "actions": ["create", "read", "run_check"],
                            },
                        },
                    )
                    assert grant.status_code == 201, "Native verification grant issuance failed"
                    headers = {"Authorization": "Bearer " + grant.json()["credential"]}
                response = await http.post(
                    "/api/verifications",
                    headers=headers,
                    json={
                        "key": "candidate",
                        "policy": "value@1",
                        "subject": api.subject.model_dump(mode="json"),
                    },
                )
                assert response.status_code == 200, response.text
                plan_id = response.json()["state"]["plan"]["plan_id"]
                assert response.json()["state"]["plan"]["root_execution_id"] == root
                response = await http.post(
                    "/api/verification-checks",
                    headers=api.human,
                    json={
                        "plan_id": plan_id,
                        "runner": "program@1",
                    },
                )
                assert response.status_code == 200, response.text
                intent = response.json()["intent_id"]
                execution = response.json()["observation"]["external_id"]
                async with asyncio.timeout(15):
                    while not marker.exists():
                        await asyncio.sleep(0.02)
                child = int(marker.read_text())
                assert os.getpgid(child) == child
                response = await http.post(
                    f"/api/verifications/{plan_id}/cancel"
                    if cancel == "plan"
                    else f"/api/executions/{root}/cancel",
                    headers=api.human,
                )
                assert response.status_code == (200 if cancel == "plan" else 202), response.text
                # No workflow/verification refresh is needed to drive cleanup.
                try:
                    async with asyncio.timeout(15):
                        while True:
                            response = await http.get(
                                f"/api/verification-checks/{intent}", headers=api.human
                            )
                            assert response.status_code == 200, response.text
                            if response.json()["job_state"] == "closed":
                                break
                            await asyncio.sleep(0.05)
                except TimeoutError:
                    observed = await http.get(f"/api/executions/{execution}", headers=api.verifier)
                    pytest.fail(
                        json.dumps(
                            {
                                "job_state": response.json()["job_state"],
                                "check_revision": response.json()["revision"],
                                "execution_phase": observed.json().get("phase"),
                                "cancel_requested": observed.json().get("cancel_requested"),
                            }
                        )
                    )
                assert not response.json()["evidence_recorded"]
                assert (await http.get(f"/api/verifications/{plan_id}", headers=api.human)).json()[
                    "outcome"
                ] == "cancelled"
                observed = await http.get(f"/api/executions/{execution}", headers=api.verifier)
                assert observed.status_code == 200 and observed.json()["phase"] == "cancelled", (
                    observed.text
                )
                assert observed.json()["cancel_requested"] is True
                assert not list((tmp_path / "check-workspaces").iterdir())
                with pytest.raises(ProcessLookupError):
                    os.kill(child, 0)
                child = None
    finally:
        # This PID/group was written by our exact controlled fixture source.
        if child is not None:
            try:
                if os.getpgid(child) == child:
                    os.killpg(child, signal.SIGKILL)
            except ProcessLookupError:
                pass
