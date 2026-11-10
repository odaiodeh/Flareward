"""Explicit source-resolution and materialization boundaries for graph or code programs."""

from pydantic import BaseModel, ConfigDict, Field, field_validator

from lumora.elements.operation import BaseOperation, OperationContext
from lumora.services.workspaces.domain.files import WorkspaceLayout, WorkspaceMode
from plugins.git.domain.repositories import GitFile, GitFileContent, GitRevision
from plugins.git.ports import GitFileReader, GitRepository


class ResolveGitRevision(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    reference: str = Field(
        default="HEAD",
        max_length=1024,
        pattern=r"^(?:HEAD|refs/(?:heads|tags)/[a-zA-Z0-9][a-zA-Z0-9._/-]*|[0-9a-f]{40}|[0-9a-f]{64})$",
    )

    @field_validator("reference")
    @classmethod
    def valid_reference(cls, value: str) -> str:
        if ".." in value or any(
            not part or part.startswith(".") or part.endswith((".", ".lock"))
            for part in value.split("/")
        ):
            raise ValueError("Expected a full branch/tag reference or immutable commit ID")
        return value


class GitCheckout(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    revision: GitRevision


class GitWorkspace(GitCheckout):
    """The checkout's initial candidate, not a claim about subsequent mutable edits."""

    workspace: str


class ResolveGitOperation(BaseOperation[ResolveGitRevision, GitRevision]):
    def __init__(self, repository: GitRepository) -> None:
        self._repository = repository

    async def execute(self, request: ResolveGitRevision, context: OperationContext) -> GitRevision:
        return await self._repository.resolve(request.reference)


class ReadGitFileOperation(BaseOperation[GitFile, GitFileContent]):
    def __init__(self, reader: GitFileReader, max_bytes: int) -> None:
        self._reader, self._max_bytes = reader, max_bytes

    async def execute(self, request: GitFile, context: OperationContext) -> GitFileContent:
        return await self._reader.read(request, max_bytes=self._max_bytes)


class CheckoutGitOperation(BaseOperation[GitCheckout, GitWorkspace]):
    def __init__(
        self,
        repository: GitRepository,
        workspace: str,
        mode: WorkspaceMode = WorkspaceMode.ISOLATED,
    ) -> None:
        self._repository, self._workspace, self._mode = repository, workspace, mode

    async def execute(self, request: GitCheckout, context: OperationContext) -> GitWorkspace:
        workspace = WorkspaceLayout.binding(
            context.execution.root_execution_id,
            context.execution.execution_id,
            context.key,
            self._workspace,
            self._mode,
        )
        await self._repository.checkout(request.revision, workspace, context.execution)
        return GitWorkspace(revision=request.revision, workspace=workspace)
