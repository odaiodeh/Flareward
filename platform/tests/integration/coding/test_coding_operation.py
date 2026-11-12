"""The installed provider operation executes its real CLI protocol through Run Engine."""

import os
from pathlib import Path

import pytest
from support.scenarios import publish, run

from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.executions.domain.models import ExecutionPhase, FailureKind
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    OperationStep,
)
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from plugins.codex.identifiers import TYPE_KEY
from plugins.codex.specification import CodexSpec


@pytest.fixture
def coding_runtime(codex_cli, tmp_path, monkeypatch):
    monkeypatch.setenv("PATH", str(codex_cli.parent) + os.pathsep + os.environ.get("PATH", ""))
    root = tmp_path / "workspaces"
    monkeypatch.setenv("LUMORA_WORKSPACE_ROOT", str(root))
    credential = tmp_path / "credential"
    credential.write_text("private-test-token")
    credential.chmod(0o600)
    monkeypatch.setenv("LUMORA_CODEX_API_KEY_FILE", str(credential))
    return root


@pytest.mark.parametrize("profile", ["thread", "process"])
@pytest.mark.parametrize("implementation", ["graph", "code"])
async def test_installed_coding_operation_runs_from_graph_or_code(
    platform, application, coding_runtime, profile, implementation
):
    application.elements.register_spec_class(CodexSpec)
    resource = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="coder"),
        type_key=TYPE_KEY,
        config={"model": "explicit-test"},
    )
    if implementation == "graph":
        program = GraphDefinition(
            resources=(resource,),
            steps=(
                OperationStep(
                    uid="work",
                    element=resource.key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={"prompt": PathBinding(path=("input", "prompt"))},
                    outputs={"values": PathBinding(path=())},
                ),
            ),
            entry="work",
            exit="work",
            outputs={"result": PathBinding(path=("values",))},
        )
    else:
        bundle = ElementBundleResolver(application.elements).resolve(resource.key, (resource,))
        program = CustomCoordinatorDefinition(
            implementation="operation",
            version="1",
            config={"bundle": bundle.model_dump(mode="json")},
        )
    first = await publish(platform, "coding-operation", program)
    await platform.programs.save(
        first.definition.model_copy(update={"execution_profile": profile}),
        platform.owner,
        expected_version=1,
    )
    revision = await platform.programs.publish(
        "coding-operation",
        platform.owner,
        expected_version=(
            await platform.programs.draft("coding-operation", platform.owner)
        ).version,
    )
    record = await run(platform, revision, {"prompt": "write evidence"})
    assert record.phase == ExecutionPhase.COMPLETED, record.failure
    outcome = record.result["result"] if implementation == "graph" else record.result
    assert outcome["content"] == "done" and outcome["commands"] == 1
    assert outcome["usage"]["input_tokens"] == 12
    workspace = coding_runtime / outcome["workspace"]
    assert (workspace / "answer.txt").read_text() == "write evidence"
    assert not Path((workspace / "home").read_text()).exists()
    assert "private-test-token" not in str(record.result)


async def test_parallel_coding_operations_use_distinct_workspaces_and_private_homes(
    platform, application, coding_runtime
):
    application.elements.register_spec_class(CodexSpec)
    resource = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="coder"),
        type_key=TYPE_KEY,
        config={"model": "explicit-test"},
    )
    bundle = ElementBundleResolver(application.elements).resolve(resource.key, (resource,))
    revision = await publish(
        platform,
        "parallel-coders",
        CustomCoordinatorDefinition(
            implementation="parallel_operation",
            version="1",
            config={"bundle": bundle.model_dump(mode="json")},
        ),
    )
    record = await run(platform, revision, {"prompt": "parallel"})
    assert record.phase == ExecutionPhase.COMPLETED, record.failure
    left, right = record.result["left"], record.result["right"]
    assert left["workspace"] != right["workspace"]
    homes = []
    for outcome in (left, right):
        workspace = coding_runtime / outcome["workspace"]
        assert (workspace / "answer.txt").read_text() == "parallel"
        homes.append((workspace / "home").read_text())
    assert homes[0] != homes[1] and all(not Path(home).exists() for home in homes)


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_composed_coding_prompt_failure_is_private_before_cli_start(
    platform, application, coding_runtime, profile
):
    application.elements.register_spec_class(CodexSpec)
    resource = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="coder"),
        type_key=TYPE_KEY,
        config={"model": "explicit-test", "instructions": "private-instructions" + "x" * 65_536},
    )
    revision = await publish(
        platform,
        "private-coding-contract",
        GraphDefinition(
            resources=(resource,),
            steps=(
                OperationStep(
                    uid="work",
                    element=resource.key,
                    execution=ExecutionSelection(profile=profile),
                    inputs={"prompt": PathBinding(path=("input", "prompt"))},
                ),
            ),
            entry="work",
            exit="work",
        ),
    )
    record = await run(platform, revision, {"prompt": "private-input"})
    assert record.phase == ExecutionPhase.FAILED
    assert record.failure.kind == FailureKind.CONTRACT
    assert "private-input" not in record.failure.message
    assert "private-instructions" not in record.failure.message
    assert not coding_runtime.exists()
