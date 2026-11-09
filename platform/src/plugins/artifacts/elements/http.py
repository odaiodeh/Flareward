"""Receiver-owned artifact credentials and bounded authenticated HTTP streams."""

import asyncio
import hashlib
import os
import stat
from collections.abc import AsyncIterable, AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Self

import httpx
from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from flareward.async_work import await_owned
from flareward.executions.domain.context import ExecutionContext
from flareward.services.access.credentials import (
    WorkflowCredentialSource,
    WorkflowCredentialUnavailable,
)
from flareward.services.artifacts.access_models import ArtifactAccessGrant, ArtifactWorkflowGrant
from flareward.services.artifacts.domain.models import (
    ArtifactRecord,
    BlobArtifactRef,
    PublishArtifact,
)
from flareward.services.artifacts.ports import (
    ArtifactConflict,
    ArtifactCredentialError,
    ArtifactIntegrityError,
    ArtifactLimitExceeded,
    ArtifactMissing,
    ArtifactStorageError,
)


class ArtifactTransportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="FLAREWARD_ARTIFACT_", extra="ignore", hide_input_in_errors=True
    )
    endpoint: AnyHttpUrl
    access_file: Path | None = None
    allow_insecure: bool = False
    timeout_seconds: float = Field(default=60, ge=1, le=1800, allow_inf_nan=False)

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
            raise ValueError("Artifact endpoint must be a server origin without credentials")
        if value.scheme != "https" and not self.allow_insecure:
            raise ValueError(
                "Artifact transfer requires HTTPS unless explicitly enabled for testing"
            )
        if self.access_file is not None and not self.access_file.is_absolute():
            raise ValueError("Artifact credential binding requires an absolute path")
        return self


class HTTPArtifactGateway:
    def __init__(
        self,
        settings: ArtifactTransportSettings,
        context: ExecutionContext,
        credential: SecretStr | None = None,
        *,
        source: WorkflowCredentialSource | None = None,
    ) -> None:
        self._settings, self._owner, self._credential = (
            settings,
            context.identity.model_copy(deep=True),
            credential,
        )
        self._http: httpx.AsyncClient | None = None
        self._context, self._source = context.model_copy(deep=True), source
        self._grant: ArtifactAccessGrant | ArtifactWorkflowGrant | None = None

    @property
    def max_bytes(self) -> int:
        if self._grant is None:
            raise RuntimeError("Artifact gateway has not been prepared")
        return self._grant.scope.max_bytes

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http is None:
            raise RuntimeError("Artifact gateway has not been prepared")
        return self._http

    def _file_credential(self) -> SecretStr:
        path = self._settings.access_file
        if path is None:
            raise ArtifactCredentialError("Artifact credential is unavailable")
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as source:
                entry = os.fstat(source.fileno())
                if (
                    not stat.S_ISREG(entry.st_mode)
                    or entry.st_mode & 0o077
                    or entry.st_uid != os.geteuid()
                ):
                    raise ArtifactCredentialError("Artifact credential file must be private")
                raw = source.read(4097)
            if not raw or len(raw) > 4096:
                raise ArtifactCredentialError("Artifact credential file is invalid")
            value = raw.decode().strip()
            if not value:
                raise ArtifactCredentialError("Artifact credential is unavailable")
            return SecretStr(value)
        except OSError, UnicodeError:
            raise ArtifactCredentialError("Artifact credential is unavailable") from None

    @staticmethod
    def _status(response: httpx.Response) -> None:
        status = response.status_code
        if status in (401, 403):
            raise ArtifactCredentialError("Artifact access is not permitted")
        if status == 404:
            raise ArtifactMissing("Artifact not found")
        if status == 409:
            raise ArtifactConflict("Artifact publication conflicts with its prior intent")
        if status == 413:
            raise ArtifactLimitExceeded("Artifact transfer exceeds its byte limit")
        if status == 422:
            raise ArtifactIntegrityError("Artifact transfer violates its content contract")
        if not 200 <= status < 300:
            raise ArtifactStorageError("Artifact service is unavailable")

    async def _request(
        self,
        method: str,
        path: str,
        *,
        content: AsyncIterable[bytes] | None = None,
        headers: dict[str, str] | None = None,
    ) -> httpx.Response:
        try:
            async with asyncio.timeout(self._settings.timeout_seconds):
                response = await self._client.request(
                    method, path, content=content, headers=headers
                )
            self._status(response)
            return response
        except TimeoutError, httpx.HTTPError:
            raise ArtifactStorageError("Artifact transfer is unavailable") from None

    async def prepare_element(self) -> None:
        credential = self._credential
        managed = credential is None and self._source is not None
        if managed:
            assert self._source is not None
            try:
                credential = await self._source.resolve(
                    "artifact@1", self._owner, self._context.root_execution_id
                )
            except WorkflowCredentialUnavailable:
                raise ArtifactStorageError("Artifact workflow credential is unavailable") from None
        if credential is None:
            credential = await await_owned(asyncio.to_thread(self._file_credential))
        self._http = httpx.AsyncClient(
            base_url=str(self._settings.endpoint),
            headers={"Authorization": "Bearer " + credential.get_secret_value()},
            timeout=self._settings.timeout_seconds,
            follow_redirects=False,
            trust_env=False,
        )
        response = await self._request("GET", "/api/artifact-access/self")
        try:
            grant = (
                ArtifactWorkflowGrant.model_validate_json(response.content)
                if managed
                else ArtifactAccessGrant.model_validate_json(response.content)
            )
        except ValidationError:
            raise ArtifactStorageError("Artifact access response violates its contract") from None
        if not grant.owner.owns(self._owner):
            raise ArtifactCredentialError("Artifact credential belongs to another owner")
        if isinstance(grant, ArtifactWorkflowGrant) and (
            grant.scope.root_execution_id != self._context.root_execution_id
        ):
            raise ArtifactCredentialError("Artifact credential belongs to another execution")
        self._grant = grant

    async def publish(
        self, request: PublishArtifact, content: AsyncIterable[bytes]
    ) -> ArtifactRecord:
        response = await self._request(
            "POST",
            "/api/artifacts",
            content=content,
            headers={"X-Artifact-Metadata": request.model_dump_json(ensure_ascii=True)},
        )
        try:
            record = ArtifactRecord.model_validate_json(response.content)
        except ValidationError:
            raise ArtifactIntegrityError(
                "Artifact publication response violates its contract"
            ) from None
        if (
            not record.owner.owns(self._owner)
            or record.reference.sha256 != request.sha256
            or record.reference.size_bytes != request.size_bytes
            or record.namespace != request.namespace
            or record.name != request.name
            or record.inputs != request.inputs
        ):
            raise ArtifactIntegrityError("Artifact publication response does not match")
        return record

    @asynccontextmanager
    async def open(self, reference: BlobArtifactRef) -> AsyncIterator[AsyncIterator[bytes]]:
        if reference.size_bytes > self.max_bytes:
            raise ArtifactLimitExceeded("Artifact transfer exceeds its byte limit")
        response = await self._request("GET", f"/api/artifacts/{reference.artifact_id}")
        try:
            record = ArtifactRecord.model_validate_json(response.content)
        except ValidationError:
            raise ArtifactIntegrityError(
                "Artifact metadata response violates its contract"
            ) from None
        if not record.owner.owns(self._owner) or record.reference != reference:
            raise ArtifactIntegrityError("Artifact download identity does not match")
        try:
            async with asyncio.timeout(self._settings.timeout_seconds):
                async with self._client.stream(
                    "GET", f"/api/artifacts/{reference.artifact_id}/content"
                ) as transfer:
                    self._status(transfer)
                    yield self._verified(transfer, reference)
        except TimeoutError, httpx.HTTPError:
            raise ArtifactStorageError("Artifact download is unavailable") from None

    @staticmethod
    async def _verified(
        response: httpx.Response, reference: BlobArtifactRef
    ) -> AsyncIterator[bytes]:
        digest, size = hashlib.sha256(), 0
        async for chunk in response.aiter_bytes(chunk_size=1_048_576):
            size += len(chunk)
            if size > reference.size_bytes:
                raise ArtifactIntegrityError("Downloaded artifact exceeds its declared size")
            digest.update(chunk)
            yield chunk
        if size != reference.size_bytes or digest.hexdigest() != reference.sha256:
            raise ArtifactIntegrityError("Downloaded artifact content does not match")

    async def aclose(self) -> None:
        if self._http is not None:
            await self._http.aclose()
            self._http = None
            self._grant = None
