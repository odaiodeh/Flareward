"""Git provenance stays with the trusted coordinator, outside evaluation workers."""

from unittest.mock import create_autospec

import pytest
from support.artifacts import inline_content
from support.operations import operation_bundle
from support.python_checks import ADDITION, addition_cases

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.ports import ProgramRuntime
from lumora.services.verification.domain.models import VerificationSubject
from lumora.services.verification.program_checks import CheckProgramInput
from plugins.git.domain.repositories import GitFileContent, GitRevision
from plugins.testing.programs.git_check import GitPythonCheck, GitPythonCheckConfig


@pytest.fixture
def git_check(application):
    runtime = create_autospec(ProgramRuntime, instance=True)
    revision = GitRevision(repository="product", commit="a" * 40)
    request = CheckProgramInput(
        intent_id="a" * 64,
        plan_id="b" * 64,
        check="tests@1",
        subject=VerificationSubject(
            kind="git-revision@1", identity=revision.model_dump(mode="json")
        ),
    )
    content = GitFileContent(revision=revision, path="answer.py", content=inline_content(ADDITION))
    config = GitPythonCheckConfig(
        reader=operation_bundle(application.elements),
        path="answer.py",
        source_execution=ExecutionSelection(profile="repository"),
        comparison=addition_cases(),
    )
    runtime.invoke_element.side_effect = [content.model_dump(mode="json"), {"values": [3, -2, 0]}]
    return GitPythonCheck(runtime, config), runtime, request, content


async def test_exact_git_source_reuses_evaluator_without_repository_or_verification_authority(
    git_check,
):
    checker, runtime, request, content = git_check
    result = await checker.run(request)
    assert result.verdict == "passed" and result.subject_fingerprint == request.subject.fingerprint
    read, evaluate = runtime.invoke_element.call_args_list
    assert read.args[1] == {"revision": request.subject.identity, "path": "answer.py"}
    assert evaluate.args[1]["source"] == content.content.model_dump(mode="json")
    assert set(evaluate.args[1]) == {"source", "cases"}
    assert "expected" not in str(evaluate.args[1])


@pytest.mark.parametrize("changed", ["revision", "path", "subject-kind"])
async def test_wrong_source_is_rejected_before_evaluation(git_check, changed):
    checker, runtime, request, content = git_check
    value = content.model_dump(mode="json")
    if changed == "revision":
        value["revision"]["commit"] = "c" * 40
    elif changed == "path":
        value["path"] = "another.py"
    else:
        request = request.model_copy(
            update={"subject": request.subject.model_copy(update={"kind": "other@1"})}
        )
    runtime.invoke_element.side_effect = [value]
    with pytest.raises(ValueError):
        await checker.run(request)
    assert runtime.invoke_element.call_count == (0 if changed == "subject-kind" else 1)
