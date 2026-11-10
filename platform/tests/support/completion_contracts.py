"""Typed deliverable examples shared by completion policy and invocation tests."""

from typing import Literal

from pydantic import BaseModel, ConfigDict

from lumora.services.artifacts.domain.models import BlobArtifactRef
from plugins.git.domain.repositories import GitRevision


class FileSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["blob-artifact@1"]
    identity: BlobArtifactRef


class GitSubject(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["git-revision@1"]
    identity: GitRevision


class FileCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: FileSubject


class GitCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    subject: GitSubject


CANDIDATES = {
    "files": FileCandidate(
        subject=FileSubject(
            kind="blob-artifact@1",
            identity=BlobArtifactRef(artifact_id="a" * 64, sha256="b" * 64, size_bytes=32),
        )
    ),
    "git": GitCandidate(
        subject=GitSubject(
            kind="git-revision@1",
            identity=GitRevision(repository="product", commit="c" * 40),
        )
    ),
}
