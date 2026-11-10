"""Scoped receiver-local review access; human response authority never travels to workers."""

import asyncio
import os
import stat
from pathlib import Path
from typing import Self

import httpx
from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from lumora.async_work import await_owned
from lumora.executions.domain.context import ExecutionContext
from lumora.services.access.credentials import (
    WorkflowCredentialSource,
    WorkflowCredentialUnavailable,
)
from lumora.services.reviews.access import ReviewGrant, review_credential_key
from lumora.services.reviews.contracts import CloseReview, OpenReview
from lumora.services.reviews.domain.models import ReviewRecord
from lumora.services.reviews.ports import (
    ReviewConflict,
    ReviewCredentialError,
    ReviewMissing,
    ReviewUnavailable,
)


class ReviewTransportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="LUMORA_REVIEW_", extra="ignore", hide_input_in_errors=True
    )
    endpoint: AnyHttpUrl
    access_directory: Path | None = None
    allow_insecure: bool = False
    timeout_seconds: float = Field(default=30, ge=1, le=1800, allow_inf_nan=False)

    @model_validator(mode="after")
    def safe_endpoint(self) -> Self:
        value = self.endpoint
        if (
            value.username
            or value.password
            or value.query
            or value.fragment
            or value.path not in ("", "/")
        ):
            raise ValueError("Review endpoint must be a credential-free server origin")
        if value.scheme != "https" and not self.allow_insecure:
            raise ValueError("Review access requires HTTPS")
        if self.access_directory is not None and not self.access_directory.is_absolute():
            raise ValueError("Review credentials require an absolute directory")
        return self


class HTTPReviewGateway:
    def __init__(
        self,
        settings: ReviewTransportSettings,
        context: ExecutionContext,
        credential: SecretStr | None = None,
        *,
        source: WorkflowCredentialSource | None = None,
    ) -> None:
        self._settings, self._context, self._credential = (
            settings,
            context.model_copy(deep=True),
            credential,
        )
        self._http: httpx.AsyncClient | None = None
        self._source = source
        self._grant: ReviewGrant | None = None

    def _file_credential(self) -> SecretStr:
        directory = self._settings.access_directory
        if directory is None:
            raise ReviewCredentialError("Review credential is unavailable")
        path = directory / review_credential_key(
            self._context.identity, self._context.root_execution_id
        )
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as source:
                entry = os.fstat(source.fileno())
                if not stat.S_ISREG(entry.st_mode) or entry.st_mode & 0o077:
                    raise ReviewCredentialError("Review credential file must be private")
                value = source.read(4097)
            if not value or len(value) > 4096:
                raise ReviewCredentialError("Review credential file is invalid")
            return SecretStr(value.decode().strip())
        except OSError, UnicodeError:
            raise ReviewCredentialError("Review credential is unavailable") from None

    @staticmethod
    def _status(status: int) -> None:
        if status in (401, 403):
            raise ReviewCredentialError("Review access is not permitted")
        if status == 404:
            raise ReviewMissing("Review not found")
        if status == 409:
            raise ReviewConflict("Review conflicts with its recorded intent")
        if status == 429 or status >= 500:
            raise ReviewUnavailable()
        if not 200 <= status < 300:
            raise ValueError("Review service response violates its contract")

    async def _request(self, method: str, path: str, content: bytes | None = None) -> bytes:
        if self._http is None:
            raise RuntimeError("Review gateway has not been prepared")
        try:
            async with asyncio.timeout(self._settings.timeout_seconds):
                async with self._http.stream(method, path, content=content) as response:
                    self._status(response.status_code)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 1_048_576:
                            raise ValueError("Review response exceeds its byte limit")
                    return bytes(data)
        except TimeoutError, httpx.HTTPError:
            raise ReviewUnavailable() from None

    async def prepare_element(self) -> None:
        if not self._context.root_execution_id or not self._context.execution_id:
            raise ValueError("Review access requires execution identity")
        credential = self._credential
        if credential is None and self._source is not None:
            try:
                credential = await self._source.resolve(
                    "review@1", self._context.identity, self._context.root_execution_id
                )
            except WorkflowCredentialUnavailable:
                raise ReviewUnavailable() from None
        elif credential is None:
            credential = await await_owned(asyncio.to_thread(self._file_credential))
        self._http = httpx.AsyncClient(
            base_url=str(self._settings.endpoint),
            headers={
                "Authorization": "Bearer " + credential.get_secret_value(),
                "Content-Type": "application/json",
            },
            timeout=self._settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        content = await self._request("GET", "/api/review-access/self")
        try:
            grant = ReviewGrant.model_validate_json(content)
        except ValidationError:
            raise ValueError("Review grant violates its contract") from None
        if (
            not grant.owner.owns(self._context.identity)
            or grant.scope.root_execution_id != self._context.root_execution_id
        ):
            raise ReviewCredentialError("Review credential does not match this execution")
        self._grant = grant

    def _view(self, content: bytes) -> ReviewRecord:
        try:
            review = ReviewRecord.model_validate_json(content)
        except ValidationError:
            raise ValueError("Review response violates its contract") from None
        if (
            self._grant is None
            or not review.owner.owns(self._grant.owner)
            or review.root_execution_id != self._grant.scope.root_execution_id
            or review.policy not in self._grant.scope.policies
        ):
            raise ReviewCredentialError("Review response exceeds its scope")
        return review

    async def open(self, request: OpenReview) -> ReviewRecord:
        review = self._view(
            await self._request("POST", "/api/reviews", request.model_dump_json().encode())
        )
        if (
            review.key != request.key
            or review.execution_id != request.execution_id
            or review.specification.fingerprint != request.specification.fingerprint
        ):
            raise ValueError("Review response identifies different work")
        return review

    async def inspect(self, review_id: str) -> ReviewRecord:
        review = self._view(await self._request("GET", "/api/reviews/" + review_id))
        if review.review_id != review_id:
            raise ValueError("Review response identifies a different occurrence")
        return review

    async def close(self, request: CloseReview) -> ReviewRecord:
        review = self._view(
            await self._request(
                "POST",
                "/api/reviews/" + request.review_id + "/close",
                request.model_dump_json().encode(),
            )
        )
        if review.review_id != request.review_id:
            raise ValueError("Review response identifies a different occurrence")
        return review

    async def aclose(self) -> None:
        client, self._http = self._http, None
        if client is not None:
            await client.aclose()
