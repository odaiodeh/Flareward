"""An operator file restricts actual graph receivers using the OpenShell proxy."""

import json
from dataclasses import replace
from importlib.resources import files
from uuid import uuid4

import pytest
from mas.core.enums import ResourceCategory
from mas.domain.element_bundles import ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import ElementStep, GraphDefinition, PathBinding, ProgramDefinition
from support.http_probe import http_probe
from support.http_programs import execute_program, publish_program
from support.scenarios import resource

from config.execution_policies import load_execution_profiles
from config.platform_settings import PlatformSettings


@pytest.fixture
async def endpoints():
    async with http_probe() as first, http_probe() as second:
        yield first, second


@pytest.fixture
async def remote_backend(remote_backend, endpoints, tmp_path, restricted):
    if remote_backend.name != "openshell":
        pytest.skip("This policy contract applies to OpenShell")
    policy = json.loads(files("config").joinpath("policies/openshell-restricted.json").read_text())
    policy["network_policies"] = {
        "probe": {
            "endpoints": [
                {"host": "host.docker.internal", "port": probe.port}
                for probe in (endpoints[:1] if restricted else endpoints)
            ],
            "binaries": policy["network_policies"]["gemini"]["binaries"],
        }
    }
    path = tmp_path / "operator-policy.json"
    path.write_text(json.dumps(policy))
    settings = PlatformSettings(
        host={"runner_type": "local"},
        storage="memory",
        interactions="disabled",
        authentication="development",
        development_user="operator",
        execution_profiles={"remote": remote_backend.target},
        default_execution_profile="remote",
        execution_policy_files={"remote": path},
    )
    profiles = await load_execution_profiles(settings)
    yield replace(remote_backend, target=profiles["remote"])


@pytest.mark.parametrize("restricted", [False, True], ids=["both-reachable", "second-denied"])
@pytest.mark.parametrize(
    "retained", [False, True], ids=["invocation-owned", "retained-environment"]
)
async def test_file_policy_controls_receiver_egress(
    deployed_remote, endpoints, restricted, retained
):
    deployment = deployed_remote
    graph = GraphDefinition(
        resources=(
            resource(
                "probe",
                category=ResourceCategory.NODE,
                type_key="network_probe",
                config={
                    "urls": [
                        f"http://host.docker.internal:{probe.port}/probe" for probe in endpoints
                    ]
                },
            ),
        ),
        steps=(
            ElementStep(
                uid="probe",
                element=ResourceKey(category=ResourceCategory.NODE, rid="probe"),
                execution=(
                    ExecutionSelection(environment="sandbox")
                    if retained
                    else ExecutionSelection(profile="remote")
                ),
            ),
        ),
        entry="probe",
        exit="probe",
        outputs={"access": PathBinding(path=("output",))},
        environments={"sandbox": "remote"} if retained else {},
    )
    reference = await publish_program(
        deployment.http,
        ProgramDefinition(
            program_id="egress-policy",
            name="Egress policy",
            owner=deployment.owner,
            implementation=graph,
        ),
    )
    record = await execute_program(deployment.http, reference, uuid4().hex, {})
    assert record["phase"] == "completed", record
    access = json.loads(record["result"]["access"])
    assert access[0] == {"allowed": True, "body": endpoints[0].body}
    assert endpoints[0].requests == 1
    if restricted:
        assert not access[1]["allowed"]
        assert endpoints[1].requests == 0
    else:
        assert access[1] == {"allowed": True, "body": endpoints[1].body}
        assert endpoints[1].requests == 1
    if deployment.replay is not None:
        await deployment.replay(record["context"]["engine_handle"])
    await deployment.backend.assert_clean()
