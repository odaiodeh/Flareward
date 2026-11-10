"""Authenticated streaming transfer; application services own access and publication policy."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import ValidationError
from starlette.types import Receive, Scope, Send

from lumora.api.artifact_access import artifact_actor
from lumora.api.dependencies import get_artifacts
from lumora.async_work import await_owned
from lumora.services.artifacts.access_models import ArtifactActor
from lumora.services.artifacts.domain.models import ArtifactRecord, PublishArtifact
from lumora.services.artifacts.service import ArtifactService

router = APIRouter(
    prefix="/api/artifacts", tags=["artifacts"], dependencies=[Depends(artifact_actor)]
)
type Service = Annotated[ArtifactService, Depends(get_artifacts)]
type Caller = Annotated[ArtifactActor, Depends(artifact_actor)]


class ArtifactResponse(StreamingResponse):
    """Release the owned artifact stream even when the response consumer disconnects."""

    def __init__(self, body: AsyncGenerator[bytes], record: ArtifactRecord) -> None:
        self._body = body
        super().__init__(
            body,
            media_type=record.media_type,
            headers={
                "Content-Length": str(record.reference.size_bytes),
                "ETag": '"' + record.reference.sha256 + '"',
                "X-Content-Type-Options": "nosniff",
                "Cache-Control": "private, no-store",
                "Content-Disposition": "attachment",
                "Content-Security-Policy": "sandbox; default-src 'none'; frame-ancestors 'none'",
            },
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        try:
            await super().__call__(scope, receive, send)
        finally:
            await await_owned(self._body.aclose())


@router.post("", response_model=ArtifactRecord, status_code=201)
async def publish(
    request: Request,
    metadata: Annotated[str, Header(alias="X-Artifact-Metadata", max_length=65_536)],
    service: Service,
    caller: Caller,
) -> ArtifactRecord:
    try:
        manifest = PublishArtifact.model_validate_json(metadata)
    except ValidationError:
        raise HTTPException(
            status_code=422, detail="Invalid artifact publication metadata"
        ) from None
    return await service.publish(manifest, request.stream(), caller)


@router.get("/{artifact_id}", response_model=ArtifactRecord)
async def inspect(
    artifact_id: str, service: Service, caller: Caller, response: Response
) -> ArtifactRecord:
    response.headers["Cache-Control"] = "private, no-store"
    return await service.inspect(artifact_id, caller)


@router.get("/{artifact_id}/content")
async def content(artifact_id: str, service: Service, caller: Caller) -> StreamingResponse:
    record = await service.download(artifact_id, caller)

    async def body() -> AsyncGenerator[bytes]:
        async with service.open(record.reference, caller) as chunks:
            async for chunk in chunks:
                yield chunk

    return ArtifactResponse(body(), record)
