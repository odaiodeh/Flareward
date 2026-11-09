"""Source operations use application ports without adopting a transport protocol."""

from dataclasses import dataclass, field

import pytest
from pydantic import ValidationError

from flareward.elements.operation import OperationContext
from flareward.executions.domain.context import ExecutionContext
from flareward.services.identity.domain import Identity
from flareward.services.workspaces.domain.files import WorkspaceMode
from plugins.git.domain.repositories import GitRevision
from plugins.git.operations import (
    CheckoutGitOperation,
    GitCheckout,
    ResolveGitOperation,
    ResolveGitRevision,
)


@dataclass
class RecordingRepository:
    revision: GitRevision = field(
        default_factory=lambda: GitRevision(repository="source", commit="a" * 40)
    )
    references: list[str] = field(default_factory=list)
    workspaces: list[str] = field(default_factory=list)

    async def resolve(self, reference: str) -> GitRevision:
        self.references.append(reference)
        return self.revision

    async def checkout(
        self, revision: GitRevision, workspace: str, context: ExecutionContext
    ) -> None:
        assert revision == self.revision
        self.workspaces.append(workspace)


@pytest.fixture
def invocation():
    return OperationContext(
        execution=ExecutionContext(
            root_execution_id="root", execution_id="child", identity=Identity.user("owner")
        ),
        key="checkout",
    )


async def test_resolve_returns_an_immutable_reference_without_publishing_a_blob(invocation):
    source = RecordingRepository()
    result = await ResolveGitOperation(source).execute(
        ResolveGitRevision(reference="refs/heads/main"), invocation
    )
    assert result == source.revision
    assert result.model_dump() == {"repository": "source", "commit": "a" * 40}
    assert source.references == ["refs/heads/main"]


@pytest.mark.parametrize("mode", [WorkspaceMode.ISOLATED, WorkspaceMode.SHARED])
async def test_checkout_preserves_candidate_and_explicit_workspace_semantics(invocation, mode):
    source = RecordingRepository()
    operation = CheckoutGitOperation(source, "source", mode)
    request = GitCheckout(revision=source.revision)
    first = await operation.execute(request, invocation)
    other = await operation.execute(request, invocation.model_copy(update={"key": "another"}))
    assert first.revision == other.revision == source.revision
    assert (first.workspace == other.workspace) == (mode == WorkspaceMode.SHARED)
    assert source.workspaces == [first.workspace, other.workspace]


@pytest.mark.parametrize(
    "reference",
    [
        "main",
        "--help",
        "refs/heads/a:b",
        "HEAD~1",
        "refs/heads/a..b",
        "refs/heads/a.lock",
        "refs/heads/a/",
        "refs/heads/.hidden",
        "refs/heads/a\n",
    ],
)
def test_resolution_rejects_revision_expressions_and_refspecs(reference):
    with pytest.raises(ValidationError):
        ResolveGitRevision(reference=reference)


@pytest.mark.parametrize("size", [40, 64])
def test_candidate_accepts_full_git_object_ids(size):
    revision = GitRevision(repository="product-api", commit="a" * size)
    assert revision.commit == "a" * size


@pytest.mark.parametrize("commit", ["main", "abc123", "a" * 41, "A" * 40, "a" * 40 + "\n"])
def test_candidate_does_not_accept_mutable_or_abbreviated_revisions(commit):
    with pytest.raises(ValidationError):
        GitRevision(repository="source", commit=commit)
