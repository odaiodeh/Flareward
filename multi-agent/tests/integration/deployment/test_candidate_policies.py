"""Candidate subprocesses obey operator policy while comparison remains outside."""

import json
from importlib.resources import files

import pytest
from mas_plugins.testing.program import FunctionCase
from support.http_probe import http_probe
from support.program_check_api import prepared_verifier
from support.python_checks import addition_cases

from config.execution_policies import load_execution_profiles
from config.platform_settings import PlatformSettings

PROBE = b"""
import os
from pathlib import Path
from urllib.request import urlopen

def read(url):
    try:
        with urlopen(url, timeout=2) as response:
            return response.read(256).decode()
    except OSError:
        return 'denied'

def write(path):
    try:
        Path(path).write_text('owned candidate policy probe')
        return True
    except OSError:
        return False

def add(first, second, host_marker, strict_filesystem):
    result = {
        'first': read(first),
        'second': read(second),
        'non_root': os.getuid() != 0,
        'host_file_absent': not Path(host_marker).exists(),
        'private_environment_absent': not any(name.startswith('UNIFAI_') for name in os.environ),
    }
    if strict_filesystem:
        result.update({
            'app_write': write('/app/candidate-policy-probe'),
            'var_tmp_write': write('/var/tmp/candidate-policy-probe'),
        })
    return result
"""


@pytest.mark.parametrize("allowed", [2, 1, 0], ids=["positive", "restricted", "offline"])
async def test_candidate_policy_enforces_declared_sandbox_guarantees_in_verifier_program(
    remote_backend, mongo_database, redis_uri, tmp_path, allowed, request
):
    if remote_backend.name != "openshell":
        pytest.skip("Candidate policy enforcement requires OpenShell")
    strict = request.config.getoption("--strict-sandbox-filesystem")
    marker = tmp_path / "host-only-file"
    marker.write_text("Not mounted into the candidate sandbox")
    async with http_probe() as first, http_probe() as second:
        endpoints = (first, second)
        policy = json.loads(
            files("config").joinpath("policies/openshell-restricted.json").read_text()
        )
        binaries = policy["network_policies"]["gemini"]["binaries"]
        if strict:
            policy["landlock"]["compatibility"] = "hard_requirement"
        policy["network_policies"] = (
            {
                "owned_probes": {
                    "endpoints": [
                        {"host": "host.docker.internal", "port": probe.port}
                        for probe in endpoints[:allowed]
                    ],
                    "binaries": binaries,
                }
            }
            if allowed
            else {}
        )
        if strict and allowed == 2:
            policy["filesystem_policy"]["read_only"].remove("/app")
            policy["filesystem_policy"]["read_write"].extend(["/app", "/var/tmp"])
        path = tmp_path / "candidate-policy.json"
        path.write_text(json.dumps(policy))
        profiles = await load_execution_profiles(
            PlatformSettings(
                host={"runner_type": "local"},
                storage="memory",
                interactions="disabled",
                authentication="development",
                development_user="operator",
                execution_profiles={"candidate": remote_backend.target},
                default_execution_profile="candidate",
                execution_policy_files={"candidate": path},
            )
        )
        target = profiles["candidate"].model_copy(
            update={
                "env": {
                    **(profiles["candidate"].env or {}),
                    "UNIFAI_PYTHON_CHECK_EXECUTION_ENABLED": "true",
                    "UNIFAI_PYTHON_CHECK_DIRECTORY": "/tmp/unifai-python-checks",
                }
            }
        )
        urls = [f"http://host.docker.internal:{probe.port}/probe" for probe in endpoints]
        expected = {
            "first": first.body if allowed >= 1 else "denied",
            "second": second.body if allowed == 2 else "denied",
            "non_root": True,
            "host_file_absent": True,
            "private_environment_absent": True,
        }
        if strict:
            expected.update({"app_write": allowed == 2, "var_tmp_write": allowed == 2})
        checker = addition_cases().model_copy(
            update={
                "cases": (FunctionCase(args=(*urls, str(marker), strict), expected=expected),),
            }
        )
        async with prepared_verifier(
            mongo_database.name,
            redis_uri,
            tmp_path,
            "candidate",
            PROBE,
            checker=checker,
            target=target,
        ) as api:
            assert not api.local_evaluation_enabled
            async with api.serve("candidate-policy") as http:
                check = await api.start_check(http)
                check = await api.settled_check(http, check["intent_id"], timeout=120)
                if check["observation"]["verdict"] != "passed":
                    execution = check["observation"]["external_id"]
                    observed = await http.get(f"/api/executions/{execution}", headers=api.verifier)
                    assert observed.status_code == 200, observed.text
                    diagnostic = {
                        "verdict": check["observation"]["verdict"],
                        "phase": observed.json()["phase"],
                        "failure": observed.json().get("failure"),
                    }
                    if check["reports"]:
                        artifact = check["reports"][0]["content"]["artifact_id"]
                        report = await http.get(
                            f"/api/artifacts/{artifact}/content", headers=api.human
                        )
                        assert report.status_code == 200, report.text
                        diagnostic["controlled_report"] = report.json()
                    pytest.fail(str(diagnostic))
                assert first.requests == int(allowed >= 1)
                assert second.requests == int(allowed == 2)
                await remote_backend.assert_clean()
                assert not (tmp_path / "check-workspaces").exists()
