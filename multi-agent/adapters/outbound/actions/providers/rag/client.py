"""Async authoring probes reuse RAG's wire models without the legacy Flask client."""

import httpx
from mas.elements.providers.rag_client.models import (
    AvailableDocsResponse,
    AvailableTagsResponse,
    HealthResponse,
)
from pydantic import JsonValue, TypeAdapter


class RagActionClient:
    def __init__(self, base_url: str, *, timeout: float = 10) -> None:
        self._base_url, self._timeout = base_url.rstrip("/"), timeout

    async def _get(
        self,
        base_url: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        user_id: str = "",
    ) -> dict[str, JsonValue]:
        headers = {"X-Authenticated-User": user_id} if user_id else {}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.get(base_url.rstrip("/") + path, params=params, headers=headers)
            response.raise_for_status()
            return TypeAdapter(dict[str, JsonValue]).validate_python(response.json())

    async def get_available_tags(
        self, *, limit: int, cursor: str | None, search_regex: str | None, authenticated_user: str
    ) -> AvailableTagsResponse:
        return AvailableTagsResponse.model_validate(
            await self._get(
                self._base_url,
                "/api/docs/available.tags.get",
                params={
                    key: value
                    for key, value in {
                        "limit": limit,
                        "cursor": cursor,
                        "search_regex": search_regex,
                    }.items()
                    if value is not None
                },
                user_id=authenticated_user,
            )
        )

    async def get_available_docs(
        self, *, limit: int, cursor: str | None, search_regex: str | None, authenticated_user: str
    ) -> AvailableDocsResponse:
        return AvailableDocsResponse.model_validate(
            await self._get(
                self._base_url,
                "/api/docs/available.docs.get",
                params={
                    key: value
                    for key, value in {
                        "limit": limit,
                        "cursor": cursor,
                        "search_regex": search_regex,
                    }.items()
                    if value is not None
                },
                user_id=authenticated_user,
            )
        )

    async def health(self, base_url: str) -> HealthResponse:
        return HealthResponse.model_validate(await self._get(base_url, "/api/health/"))
