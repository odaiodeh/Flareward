"""A coding agent's reported commit must exist in the admitted retained repository."""

import json
from unittest.mock import create_autospec

import pytest
from support.git_resources import git_resources
from support.operations import operation_bundle

from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.ports import ProgramRuntime
from plugins.adlc_git.programs.coding import (
    CodingGitCandidate,
    CodingGitConfig,
    CodingGitWork,
)
from plugins.git.domain.repositories import GitRevision
from plugins.git.elements.specification import ELEMENT_SPECIFICATIONS


@pytest.fixture
def candidate(application):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    resources = git_resources()
    runtime = create_autospec(ProgramRuntime, instance=True)
    config = CodingGitConfig(
        coding=operation_bundle(application.elements),
        loader=operation_bundle(application.elements),
        resolver=ElementBundleResolver(application.elements).resolve(resources[1].key, resources),
        repository="product",
        execution=ExecutionSelection(profile="coding"),
        artifact_execution=ExecutionSelection(profile="storage"),
        repository_execution=ExecutionSelection(profile="repository"),
    )
    revision = GitRevision(repository="product", commit="a" * 40)
    runtime.invoke_element.side_effect = [
        {"content": revision.model_dump_json(), "workspace": "owned/work"},
        revision.model_dump(mode="json"),
    ]
    return CodingGitCandidate(runtime, config), runtime, config, revision


async def test_reported_commit_is_resolved_on_separate_repository_placement(candidate):
    service, runtime, config, revision = candidate
    result = await service.run(CodingGitWork(task={"prompt": "Implement"}, attempt=0))
    assert result.subject.kind == "git-revision@1"
    assert result.subject.identity == revision.model_dump(mode="json")
    code, resolve = runtime.invoke_element.call_args_list
    assert code.kwargs["execution"] == config.execution
    assert resolve.kwargs["execution"] == config.repository_execution
    assert resolve.args[1] == {"reference": revision.commit}
    assert "publish" in code.args[1]["context"]


@pytest.mark.parametrize(
    "invalid", ["prose", "mutable", "repository", "unavailable", "different-commit"]
)
async def test_unresolved_or_invalid_report_cannot_become_a_candidate(candidate, invalid):
    service, runtime, _, revision = candidate
    reported = revision.model_dump(mode="json")
    if invalid == "mutable":
        reported["commit"] = "refs/heads/private-branch"
    if invalid == "repository":
        reported["repository"] = "private-repository"
    content = "private-agent-answer" if invalid == "prose" else json.dumps(reported)
    response = (
        ValueError("Repository unavailable")
        if invalid == "unavailable"
        else revision.model_dump(mode="json")
    )
    if invalid == "different-commit":
        response["commit"] = "b" * 40
    runtime.invoke_element.side_effect = [{"content": content, "workspace": "owned/work"}, response]
    with pytest.raises(ValueError) as error:
        await service.run(CodingGitWork(task={"prompt": "Implement"}, attempt=0))
    assert "private" not in str(error.value)
    assert runtime.invoke_element.call_count == (
        1 if invalid in {"prose", "mutable", "repository"} else 2
    )
