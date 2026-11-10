"""Coding work uses narrow application ports without graph or CLI dependencies."""

import asyncio
from dataclasses import dataclass, field
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from support.operations import operation_context

from lumora.elements.coding.contracts import (
    CodingAgentError,
    CodingInput,
    CodingRequest,
    CodingResult,
    WorkspacePreparation,
)
from lumora.elements.coding.operation import CodingOperation
from lumora.services.artifacts.domain.models import BlobArtifactRef
from lumora.services.workspaces.domain.files import ArtifactFile, WorkspaceMode


@dataclass
class RecordingCoder:
    requests: list[CodingRequest] = field(default_factory=list)
    failure: bool = False

    async def execute(self, request: CodingRequest) -> CodingResult:
        self.requests.append(request)
        if self.failure:
            raise CodingAgentError("Coding failed")
        return CodingResult(content="implemented")


async def test_coding_accepts_explicit_input_and_returns_typed_result():
    coder = RecordingCoder()
    operation = CodingOperation(coder, "work", "Implement carefully")
    result = await operation.execute(
        CodingInput(prompt="Fix the calculation", context="previous result"), operation_context()
    )
    request = coder.requests[0]
    assert "Fix the calculation" in request.prompt and "previous result" in request.prompt
    assert "Implement carefully" in request.prompt
    assert result.content == "implemented" and result.workspace == request.workspace


async def test_default_isolation_distinguishes_calls_and_children_and_is_stable_for_retries():
    coder = RecordingCoder()
    operation = CodingOperation(coder, "work", "")
    for scope in (
        operation_context(),
        operation_context(),
        operation_context(key="other"),
        operation_context(execution="child"),
    ):
        await operation.execute(CodingInput(prompt="work"), scope)
    workspaces = [request.workspace for request in coder.requests]
    assert workspaces[0] == workspaces[1]
    assert len(set(workspaces)) == 3


async def test_explicit_sharing_reuses_root_workspace_and_separates_other_roots():
    coder = RecordingCoder()
    operation = CodingOperation(coder, "shared", "", WorkspaceMode.SHARED)
    for scope in (
        operation_context(),
        operation_context(execution="child", key="other"),
        operation_context(root="other"),
    ):
        await operation.execute(CodingInput(prompt="work"), scope)
    assert coder.requests[0].workspace == coder.requests[1].workspace
    assert coder.requests[0].workspace != coder.requests[2].workspace
    assert coder.requests[0].workspace.endswith("/shared")


async def test_failed_coding_propagates_without_a_success_result():
    operation = CodingOperation(RecordingCoder(failure=True), "work", "")
    with pytest.raises(CodingAgentError):
        await operation.execute(CodingInput(prompt="work"), operation_context())


@pytest.mark.parametrize("scope", [operation_context(root=""), operation_context(execution="")])
async def test_missing_execution_identity_fails_before_calling_provider(scope):
    coder = RecordingCoder()
    operation = CodingOperation(coder, "work", "")
    with pytest.raises(ValueError, match="execution identity"):
        await operation.execute(CodingInput(prompt="work"), scope)
    assert not coder.requests


@pytest.fixture
def input_file():
    return ArtifactFile(
        artifact=BlobArtifactRef(artifact_id="a" * 64, sha256="b" * 64, size_bytes=5),
        path="src/previous.py",
    )


async def test_preparation_uses_the_actual_isolated_workspace_before_coding(input_file):
    coder = RecordingCoder()
    preparation = create_autospec(WorkspacePreparation, instance=True)
    scope = operation_context()

    async def prepare(files, workspace, execution):
        assert not coder.requests
        assert files == (input_file,) and workspace.endswith("/work")
        assert execution == scope.execution

    preparation.prepare.side_effect = prepare
    operation = CodingOperation(coder, "work", "", preparation=preparation)
    result = await operation.execute(CodingInput(prompt="Repair", files=(input_file,)), scope)
    assert preparation.prepare.await_args.args[1] == result.workspace
    assert input_file.path in coder.requests[0].prompt


async def test_missing_preparation_cannot_ignore_requested_inputs(input_file):
    coder = RecordingCoder()
    with pytest.raises(CodingAgentError, match="preparation provider"):
        await CodingOperation(coder, "work", "").execute(
            CodingInput(prompt="Repair", files=(input_file,)), operation_context()
        )
    assert not coder.requests


@pytest.mark.parametrize("failure", [PermissionError("denied"), asyncio.CancelledError()])
async def test_failed_or_cancelled_preparation_never_starts_coding(input_file, failure):
    coder = RecordingCoder()
    preparation = create_autospec(WorkspacePreparation, instance=True)
    preparation.prepare.side_effect = failure
    with pytest.raises(type(failure)):
        await CodingOperation(coder, "work", "", preparation=preparation).execute(
            CodingInput(prompt="Repair", files=(input_file,)), operation_context()
        )
    assert not coder.requests


@pytest.mark.parametrize("path", ["src//previous.py", "src/./previous.py"])
def test_aliasing_input_destinations_are_rejected(input_file, path):
    with pytest.raises(ValidationError, match="distinct destination"):
        CodingInput(
            prompt="Repair", files=(input_file, input_file.model_copy(update={"path": path}))
        )
