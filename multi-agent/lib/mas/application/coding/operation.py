"""Reusable coding behavior without graph-state or provider dependencies."""

from mas.application.coding.contracts import (
    CodingAgent,
    CodingAgentError,
    CodingInput,
    CodingOutcome,
    CodingRequest,
    WorkspacePreparation,
)
from mas.application.elements.operation import BaseOperation, OperationContext
from mas.domain.files import WorkspaceLayout, WorkspaceMode


class CodingOperation(BaseOperation[CodingInput, CodingOutcome]):
    def __init__(
        self,
        agent: CodingAgent,
        workspace: str,
        instructions: str,
        workspace_mode: WorkspaceMode = WorkspaceMode.ISOLATED,
        preparation: WorkspacePreparation | None = None,
    ) -> None:
        self._agent = agent
        self._workspace = workspace
        self._instructions = instructions
        self._workspace_mode = workspace_mode
        self._preparation = preparation

    async def execute(self, request: CodingInput, context: OperationContext) -> CodingOutcome:
        root = context.execution.root_execution_id
        if not root or not context.execution.execution_id:
            raise ValueError("Coding workspace requires root and execution identity")
        workspace = WorkspaceLayout.binding(
            root, context.execution.execution_id, context.key, self._workspace, self._workspace_mode
        )
        if request.files and self._preparation is None:
            raise CodingAgentError("Coding workspace inputs require a preparation provider")
        manifest = (
            "Workspace input files:\n" + "\n".join(file.path for file in request.files)
            if request.files
            else ""
        )
        prompt = "\n\n".join(
            value
            for value in (self._instructions, request.prompt, request.context, manifest)
            if value
        )
        work = CodingRequest(prompt=prompt, workspace=workspace)
        if request.files and self._preparation is not None:
            await self._preparation.prepare(request.files, workspace, context.execution)
        result = await self._agent.execute(work)
        return CodingOutcome(**result.model_dump(), workspace=workspace)
