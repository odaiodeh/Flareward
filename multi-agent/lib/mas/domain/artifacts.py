"""Immutable durable content identities, separate from mutable workspace locations."""

import base64
import hashlib
from datetime import UTC, datetime
from typing import Annotated, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from mas.core.identity import Identity

type ArtifactId = Annotated[str, Field(pattern=r"^[a-f0-9]{64}$")]
type ArtifactNamespace = Annotated[str, Field(min_length=1, max_length=128)]
type ArtifactMediaType = Annotated[
    str,
    Field(
        max_length=255,
        pattern=r"^[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*/[A-Za-z0-9][A-Za-z0-9!#$&^_.+-]*$",
    ),
]


class ContentIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    size_bytes: int = Field(ge=0)


class BlobArtifactRef(ContentIdentity):
    artifact_id: ArtifactId


def _decode_inline(identity: ContentIdentity, data: str) -> bytes:
    if identity.size_bytes > 1_048_576:
        raise ValueError("Inline content exceeds its byte limit")
    content = base64.b64decode(data, validate=True)
    if (
        len(content) != identity.size_bytes
        or hashlib.sha256(content).hexdigest() != identity.sha256
    ):
        raise ValueError("Inline content does not match its content identity")
    return content


class InlineContent(BaseModel):
    """Small verified bytes, without implying publication or granting storage access."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    identity: ContentIdentity
    data: str = Field(max_length=1_398_104, repr=False)

    def decoded(self) -> bytes:
        return _decode_inline(self.identity, self.data)

    @model_validator(mode="after")
    def exact_content(self) -> Self:
        self.decoded()
        return self


class InlineArtifact(BaseModel):
    """Bounded content transport when a receiver must not receive a storage credential."""

    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    reference: BlobArtifactRef
    data: str = Field(max_length=1_398_104, repr=False)

    def decoded(self) -> bytes:
        return _decode_inline(self.reference, self.data)

    @model_validator(mode="after")
    def exact_content(self) -> Self:
        self.decoded()
        return self


class PublishArtifact(ContentIdentity):
    key: str = Field(min_length=1, max_length=256)
    namespace: ArtifactNamespace = "default"
    name: str = Field(min_length=1, max_length=255)
    media_type: ArtifactMediaType = "application/octet-stream"
    inputs: tuple[BlobArtifactRef, ...] = Field(default=(), max_length=64)


class ArtifactRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    reference: BlobArtifactRef
    owner: Identity
    namespace: ArtifactNamespace
    name: str = Field(min_length=1, max_length=255)
    media_type: ArtifactMediaType
    inputs: tuple[BlobArtifactRef, ...] = Field(default=(), max_length=64)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    def matches(self, other: Self) -> bool:
        """A retried publication may not change content, lineage, or ownership."""
        return (
            self.owner.owns(other.owner)
            and self.model_copy(update={"owner": other.owner, "created_at": other.created_at})
            == other
        )
