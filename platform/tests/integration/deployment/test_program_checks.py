"""Installed Python verifier via public signed API, remote placement and retirement."""

import asyncio
import json
from uuid import uuid4

import pytest
from support.program_check_api import prepared_verifier
from support.python_checks import ADDITION, SUBTRACTION, addition_cases

from plugins.testing.programs.python_check import FunctionCase


@pytest.fixture
def checker_target(remote_backend):
    return remote_backend.target.model_copy(
        update={
            "env": {
                **(remote_backend.target.env or {}),
                "LUMORA_PYTHON_CHECK_EXECUTION_ENABLED": "true",
                "LUMORA_PYTHON_CHECK_DIRECTORY": "/tmp/lumora-python-checks",
            }
        }
    )


@pytest.mark.parametrize("candidate,outcome", [(ADDITION, "accepted"), (SUBTRACTION, "rejected")])
async def test_remote_python_verifier_uses_pinned_program_without_storage_credentials(
    remote_backend,
    checker_target,
    mongo_database,
    redis_uri,
    tmp_path,
    candidate,
    outcome,
    record_property,
):
    backend = remote_backend
    target = checker_target
    marker = tmp_path / "host-only-marker"
    marker.write_text("Not mounted into the receiver")
    # Controlled test code keeps a receiver observable briefly and verifies that
    # the subprocess receives neither host files nor inherited service settings.
    source = (
        "import os, time\nfrom pathlib import Path\n"
        "assert os.getuid() != 0\n"
        "assert Path('/opt/lumora-e2e-receiver').read_text() == 'lumora-platform-e2e-v1'\n"
        "assert not Path('/var/run/secrets/kubernetes.io/serviceaccount/token').exists()\n"
        f"assert not Path({str(marker)!r}).exists()\n"
        "assert not any(name.startswith('LUMORA_') for name in os.environ)\n"
        "time.sleep(3)\n"
    ).encode() + candidate
    async with prepared_verifier(
        mongo_database.name, redis_uri, tmp_path, "checker", source, target=target
    ) as api:
        async with api.serve("remote-check") as http:
            check = await api.start_check(http)
            if backend.inspect_receiver is not None:
                proof = await backend.inspect_receiver()
                assert proof.namespace == backend.namespace
                assert proof.image == target.image and proof.image_id
                assert proof.non_root and not proof.host_access and not proof.mounted_secrets
                assert proof.environment_names == frozenset(target.env) | {"RUNENGINE_PARAMS"}
                record_property("receiver_namespace", proof.namespace)
                record_property("receiver_pod", proof.pod)
                record_property("receiver_image", proof.image)
                record_property("receiver_image_id", proof.image_id)
            check = await api.settled_check(http, check["intent_id"], timeout=75)
            execution = check["observation"]["external_id"]
            assert (
                await http.get(f"/api/executions/{execution}", headers=api.human)
            ).status_code == 403
            observed = await http.get(f"/api/executions/{execution}", headers=api.verifier)
            assert observed.status_code == 200, observed.text
            assert observed.json()["program"] == api.reference.model_dump(mode="json")
            assert observed.json()["owner"]["id"] == api.operator.id
            assert observed.json()["workflow_access_approval"] is None
            assert observed.json()["inputs"]["artifact"]["reference"] == api.subject.identity
            assert (
                await http.get(f"/api/verifications/{check['plan']['plan_id']}", headers=api.human)
            ).json()["outcome"] == outcome
            reference = check["reports"][0]["content"]
            response = await http.get(
                f"/api/artifacts/{reference['artifact_id']}/content", headers=api.human
            )
            assert response.status_code == 200, response.text
            report = json.loads(response.content)
            assert report["subject_fingerprint"] == api.subject.fingerprint
            assert report["verdict"] == ("passed" if outcome == "accepted" else "failed")
            await backend.assert_clean()
            assert not (tmp_path / "check-workspaces").exists()
        async with api.serve("restored") as http:
            restored = await http.get(
                f"/api/verification-checks/{check['intent_id']}", headers=api.human
            )
            assert restored.status_code == 200 and restored.json() == check, restored.text
            restored_report = await http.get(
                f"/api/artifacts/{reference['artifact_id']}/content", headers=api.human
            )
            assert restored_report.status_code == 200
            assert restored_report.content == response.content
            await backend.assert_clean()


async def test_cancelled_remote_verifier_drains_and_removes_owned_receiver(
    remote_backend, checker_target, mongo_database, redis_uri, tmp_path
):
    if remote_backend.inspect_receiver is None:
        pytest.skip("This cancellation scenario requires an observable invocation-owned pod")
    checker = addition_cases(timeout_seconds=6)
    async with prepared_verifier(
        mongo_database.name,
        redis_uri,
        tmp_path,
        "checker",
        b"while True:\n    pass\n",
        checker=checker,
        target=checker_target,
    ) as api:
        async with api.serve("cancel-remote") as http:
            check = await api.start_check(http)
            await remote_backend.inspect_receiver()
            intent, plan = check["intent_id"], check["plan"]["plan_id"]
            execution = check["observation"]["external_id"]
            response = await http.post(f"/api/verifications/{plan}/cancel", headers=api.human)
            assert response.status_code == 200, response.text
            # Observe normal upkeep; refreshing a check must not drive retirement.
            async with asyncio.timeout(45):
                while True:
                    response = await http.get(
                        f"/api/verification-checks/{intent}", headers=api.human
                    )
                    assert response.status_code == 200, response.text
                    check = response.json()
                    if check["job_state"] == "closed":
                        break
                    await asyncio.sleep(0.1)
            assert not check["evidence_recorded"] and not check["reports"]
            observed = await http.get(f"/api/executions/{execution}", headers=api.verifier)
            assert observed.status_code == 200, observed.text
            assert observed.json()["phase"] == "cancelled"
            assert observed.json()["cancel_requested"] is True
            assert (await http.get(f"/api/verifications/{plan}", headers=api.human)).json()[
                "outcome"
            ] == "cancelled"
            await remote_backend.assert_clean()
            assert not (tmp_path / "check-workspaces").exists()


async def test_candidate_parent_environment_cannot_supply_comparator_answers(
    remote_backend, checker_target, mongo_database, redis_uri, tmp_path
):
    if remote_backend.inspect_receiver is None:
        pytest.skip("The parent-environment probe requires an invocation-owned pod")
    # The canary exists only in the trusted Program configuration. Candidate source
    # deliberately inspects its own receiver parent, never another pod or host.
    config = addition_cases().model_copy(
        update={"cases": (FunctionCase(args=(17,), expected=uuid4().hex),)}
    )
    source = rb"""
import json
import os
from pathlib import Path

environment = Path(f'/proc/{os.getppid()}/environ').read_bytes().split(b'\0')
serialized = next(item.split(b'=', 1)[1] for item in environment
                  if item.startswith(b'RUNENGINE_PARAMS='))
invocation = json.loads(serialized)
assert set(invocation['kwargs']['inputs']) == {'artifact', 'cases'}

def answers(value):
    if isinstance(value, dict):
        if 'expected' in value:
            yield value['expected']
        for nested in value.values():
            yield from answers(nested)
    elif isinstance(value, list):
        for nested in value:
            yield from answers(nested)

recovered = list(answers(invocation))
def add(value):
    return recovered[0] if recovered else 'no comparator answer in receiver'
"""
    async with prepared_verifier(
        mongo_database.name,
        redis_uri,
        tmp_path,
        "checker",
        source,
        checker=config,
        target=checker_target,
    ) as api:
        async with api.serve("parent-environment") as http:
            check = await api.start_check(http)
            check = await api.settled_check(http, check["intent_id"], timeout=75)
            assert check["observation"]["verdict"] == "failed"
            reference = check["reports"][0]["content"]
            response = await http.get(
                f"/api/artifacts/{reference['artifact_id']}/content", headers=api.human
            )
            assert response.status_code == 200, response.text
            result = json.loads(response.content)
            assert result["details"]["failures"] == [
                {
                    "case": 0,
                    "expected": config.cases[0].expected,
                    "actual": "no comparator answer in receiver",
                }
            ]
            await remote_backend.assert_clean()
