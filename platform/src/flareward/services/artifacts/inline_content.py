"""Bounded stream/value conversion shared by ordinary artifact transfer operations."""

import base64
from collections.abc import AsyncIterable, AsyncIterator

from flareward.services.artifacts.domain.models import ContentIdentity, InlineContent
from flareward.services.artifacts.ports import ArtifactIntegrityError, ArtifactLimitExceeded


async def collect_content(
    source: AsyncIterable[bytes], identity: ContentIdentity, max_bytes: int
) -> InlineContent:
    if identity.size_bytes > max_bytes:
        raise ArtifactLimitExceeded("Content exceeds its transfer byte limit")
    content = bytearray()
    async for chunk in source:
        if len(content) + len(chunk) > max_bytes:
            raise ArtifactLimitExceeded("Content exceeds its transfer byte limit")
        content.extend(chunk)
    try:
        return InlineContent(identity=identity, data=base64.b64encode(content).decode("ascii"))
    except ValueError:
        raise ArtifactIntegrityError("Transferred content does not match its identity") from None


async def content_chunks(content: InlineContent) -> AsyncIterator[bytes]:
    yield content.decoded()
