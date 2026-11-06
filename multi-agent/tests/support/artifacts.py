"""Portable artifact scenarios shared across policy, storage and HTTP contracts."""

import base64
import hashlib
from collections.abc import AsyncIterator

from mas.domain.artifacts import (
    BlobArtifactRef,
    ContentIdentity,
    InlineArtifact,
    InlineContent,
    PublishArtifact,
)


def publication(
    data: bytes = b"candidate",
    *,
    key: str = "write",
    namespace: str = "default",
    inputs: tuple[BlobArtifactRef, ...] = (),
) -> PublishArtifact:
    return PublishArtifact(
        key=key,
        namespace=namespace,
        name="candidate.txt",
        media_type="text/plain",
        sha256=hashlib.sha256(data).hexdigest(),
        size_bytes=len(data),
        inputs=inputs,
    )


async def chunks(data: bytes = b"candidate") -> AsyncIterator[bytes]:
    for offset in range(0, len(data), 3):
        yield data[offset : offset + 3]


def inline_artifact(content: bytes = b"candidate") -> InlineArtifact:
    return InlineArtifact(
        reference=BlobArtifactRef(
            artifact_id="f" * 64,
            sha256=hashlib.sha256(content).hexdigest(),
            size_bytes=len(content),
        ),
        data=base64.b64encode(content).decode(),
    )


def inline_content(content: bytes = b"candidate") -> InlineContent:
    return InlineContent(
        identity=ContentIdentity(
            sha256=hashlib.sha256(content).hexdigest(), size_bytes=len(content)
        ),
        data=base64.b64encode(content).decode(),
    )
