"""Operator policy files become validated execution snapshots, outside program data."""

import json
from importlib.resources import files

import pytest
from mas.core.execution_context import ExecutionContext
from outbound.run_engine.compiler import ProgramCompiler
from pydantic import ValidationError
from runengine.coordination.models import RunRequest
from runengine.invocation.config import OpenShellRunnerConfig, ThreadRunnerConfig
from runengine.programs.graph.inputs import GraphProgramInput
from support.scenarios import echo_graph, publish

from bootstrap.platform import compose_platform
from config.execution_policies import load_execution_profiles
from config.platform_settings import PlatformSettings


@pytest.fixture
def policy_file(tmp_path):
    path = tmp_path / "policy.json"
    path.write_text(files("config").joinpath("policies/openshell-restricted.json").read_text())
    return path


@pytest.fixture
def policy_settings(policy_file):
    return PlatformSettings(
        host={"runner_type": "local"},
        storage="memory",
        authentication="development",
        development_user="alice",
        interactions="disabled",
        execution_profiles={
            "trusted-worker": ThreadRunnerConfig(),
            "restricted": OpenShellRunnerConfig(
                endpoint="https://gateway.invalid", image="receiver"
            ),
        },
        execution_policy_files={"restricted": policy_file},
    )


async def test_file_policy_is_pinned_in_compiled_work_without_mutating_settings(
    policy_settings,
    policy_file,
    application,
):
    profiles = await load_execution_profiles(policy_settings)
    compiler = ProgramCompiler(
        application.programs,
        application.elements,
        application.applications,
        profiles,
        policy_settings.default_execution_profile,
    )
    expected = profiles["restricted"].model_dump(mode="json")
    profiles["restricted"].policy.network_policies["gemini"].endpoints[0].host = "changed.example"
    policy_file.write_text("invalid after startup")
    revision = await publish(application, "restricted-program", echo_graph("restricted"))
    request = await compiler.compile(
        revision,
        application.owner,
        ExecutionContext(identity=application.owner),
    )
    graph_request = RunRequest.model_validate(request.input["graph_request"])
    graph = GraphProgramInput.model_validate(graph_request.input)
    assert graph.targets["echo"] == expected
    assert str(policy_file) not in request.model_dump_json()
    assert policy_settings.execution_profiles["restricted"].policy is None
    assert expected["policy"]["filesystem_policy"]["read_write"] == [
        "/sandbox",
        "/tmp",
        "/dev/null",
    ]


@pytest.mark.parametrize("source", ["missing", "directory", "invalid-json", "invalid-policy"])
async def test_bad_policy_refuses_startup_before_opening_clients(
    policy_settings,
    policy_file,
    monkeypatch,
    source,
):
    if source == "missing":
        policy_file.unlink()
    elif source == "directory":
        policy_file.unlink()
        policy_file.mkdir()
    elif source == "invalid-json":
        policy_file.write_text('{"private-data": "must-not-log"')
    else:
        policy_file.write_text(json.dumps({"unknown-private-field": "must-not-log"}))

    def unexpected_host(*args, **kwargs):
        pytest.fail("Policy failure reached engine client allocation")

    monkeypatch.setattr("bootstrap.platform.RunHostBuilder.create", unexpected_host)
    with pytest.raises(ValueError, match="Cannot load execution policy.*restricted") as error:
        async with compose_platform(policy_settings):
            pytest.fail("Invalid policy started a platform")
    assert "must-not-log" not in str(error.value)
    assert error.value.__cause__ is None


@pytest.mark.parametrize("case", ["unknown-profile", "thread", "relative", "inline", "existing"])
def test_policy_file_configuration_refuses_ambiguous_or_ineffective_settings(policy_settings, case):
    data = policy_settings.model_dump(mode="python")
    if case == "unknown-profile":
        data["execution_policy_files"] = {"unknown": "/policy.json"}
    elif case == "thread":
        data["execution_profiles"]["restricted"] = {"runner_type": "thread"}
    elif case == "relative":
        data["execution_policy_files"] = {"restricted": "relative-policy.json"}
    elif case == "inline":
        data["execution_profiles"]["restricted"]["policy"] = {}
    else:
        data["execution_profiles"]["restricted"].update(image=None, sandbox_id="existing")
    with pytest.raises(ValidationError):
        PlatformSettings.model_validate(data)


async def test_policy_files_use_the_same_environment_configuration_as_profiles(
    policy_settings,
    policy_file,
    monkeypatch,
):
    data = policy_settings.model_dump(mode="python")
    data.pop("execution_policy_files")
    monkeypatch.setenv(
        "UNIFAI_EXECUTION_POLICY_FILES", json.dumps({"restricted": str(policy_file)})
    )
    settings = PlatformSettings.model_validate(data)
    profiles = await load_execution_profiles(settings)
    assert profiles["restricted"].policy.network_policies["gemini"].endpoints[0].host == (
        "generativelanguage.googleapis.com"
    )


async def test_platform_starts_with_a_valid_policy_and_an_unused_remote_profile(
    policy_settings,
    application,
):
    async with compose_platform(
        policy_settings,
        elements=application.elements,
        applications=application.applications,
    ) as services:
        assert services.programs is not None
