"""Coding workflow behavior uses a port double without loading any CLI or engine."""

from dataclasses import dataclass, field

import pytest
from mas.application.coding.contracts import CodingAgentError, CodingRequest, CodingResult
from mas.application.coding.node import CodingAgentNode
from mas.core.execution_context import ExecutionContext, ExecutionContextHolder
from mas.core.identity import Identity
from mas.graph.models import StepContext
from mas.graph.state.graph_state import GraphState


@dataclass
class RecordingCoder:
    requests: list[CodingRequest] = field(default_factory=list)
    failure: bool = False

    async def execute(self, request: CodingRequest) -> CodingResult:
        self.requests.append(request)
        if self.failure:
            raise CodingAgentError("Coding failed")
        return CodingResult(content="implemented")


def node(coder, root, *, workspace="shared"):
    holder = ExecutionContextHolder()
    holder.context = ExecutionContext(root_execution_id=root, identity=Identity.user("owner"))
    implementation = CodingAgentNode(coder, holder, workspace, "Implement carefully")
    implementation.set_context(StepContext(uid="coder"))
    return implementation


async def test_coding_uses_explicit_workflow_input_and_commits_typed_result():
    coder = RecordingCoder()
    state = GraphState(user_prompt="Fix the calculation", output="previous result")
    result = await node(coder, "root")(state, {})
    request = coder.requests[0]
    assert "Fix the calculation" in request.prompt and "previous result" in request.prompt
    assert "Implement carefully" in request.prompt
    assert result.output == "implemented" and result.messages[-1].content == "implemented"
    assert CodingResult.model_validate_json(result.nodes_output["coder"]).content == "implemented"


async def test_root_namespace_shares_with_siblings_and_separates_other_executions():
    coder = RecordingCoder()
    for root in ("first", "first", "second"):
        await node(coder, root)(GraphState(user_prompt="work"), {})
    assert coder.requests[0].workspace == coder.requests[1].workspace
    assert coder.requests[0].workspace != coder.requests[2].workspace
    assert coder.requests[0].workspace.endswith("/shared")


async def test_failed_coding_does_not_publish_success_state():
    state = GraphState(user_prompt="work", output="previous")
    with pytest.raises(CodingAgentError):
        await node(RecordingCoder(failure=True), "root")(state, {})
    assert state.output == "previous" and not state.nodes_output and not state.messages


async def test_missing_root_identity_cannot_share_an_unscoped_workspace():
    coder = RecordingCoder()
    with pytest.raises(ValueError, match="root execution identity"):
        await node(coder, "")(GraphState(user_prompt="work"), {})
    assert not coder.requests
