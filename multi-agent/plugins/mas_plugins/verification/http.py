"""Scoped receiver-local HTTP verification access; no verifier/CI credentials."""

import asyncio
import os
import stat
from pathlib import Path
from typing import Self

import httpx
from mas.application.access.credentials import (
    WorkflowCredentialSource,
    WorkflowCredentialUnavailable,
)
from mas.application.verification.access_models import (
    VerificationAccessGrant,
    verification_credential_key,
)
from mas.application.verification.check_ports import StartCheckRun
from mas.application.verification.models import StartVerification, VerificationView
from mas.application.verification.ports import (
    VerificationConflict,
    VerificationCredentialError,
    VerificationMissing,
    VerificationUnavailable,
)
from mas.core.async_work import await_owned
from mas.domain.check_runs import CheckRun
from mas.domain.execution.context import ExecutionContext
from pydantic import AnyHttpUrl, Field, SecretStr, ValidationError, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class VerificationTransportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="UNIFAI_VERIFICATION_", extra="ignore", hide_input_in_errors=True
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
            raise ValueError("Verification endpoint must be a credential-free server origin")
        if value.scheme != "https" and not self.allow_insecure:
            raise ValueError("Verification access requires HTTPS")
        if self.access_directory is not None and not self.access_directory.is_absolute():
            raise ValueError("Verification credentials require an absolute directory")
        return self


class HTTPVerificationGateway:
    def __init__(
        self,
        settings: VerificationTransportSettings,
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
        self._grant: VerificationAccessGrant | None = None

    def _file_credential(self) -> SecretStr:
        directory = self._settings.access_directory
        if directory is None:
            raise VerificationCredentialError("Verification credential is unavailable")
        path = directory / verification_credential_key(
            self._context.identity, self._context.root_execution_id
        )
        try:
            descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(descriptor, "rb") as source:
                entry = os.fstat(source.fileno())
                if not stat.S_ISREG(entry.st_mode) or entry.st_mode & 0o077:
                    raise VerificationCredentialError(
                        "Verification credential file must be private"
                    )
                value = source.read(4097)
            if not value or len(value) > 4096:
                raise VerificationCredentialError("Verification credential file is invalid")
            return SecretStr(value.decode().strip())
        except OSError, UnicodeError:
            raise VerificationCredentialError("Verification credential is unavailable") from None

    @staticmethod
    def _status(status: int) -> None:
        if status in (401, 403):
            raise VerificationCredentialError("Verification access is not permitted")
        if status == 404:
            raise VerificationMissing("Verification not found")
        if status == 409:
            raise VerificationConflict("Verification conflicts with its recorded intent")
        if status == 429 or status >= 500:
            raise VerificationUnavailable()
        if not 200 <= status < 300:
            raise ValueError("Verification service response violates its contract")

    async def _request(self, method: str, path: str, content: bytes | None = None) -> bytes:
        if self._http is None:
            raise RuntimeError("Verification gateway has not been prepared")
        try:
            async with asyncio.timeout(self._settings.timeout_seconds):
                async with self._http.stream(method, path, content=content) as response:
                    self._status(response.status_code)
                    data = bytearray()
                    async for chunk in response.aiter_bytes():
                        data.extend(chunk)
                        if len(data) > 1_048_576:
                            raise ValueError("Verification response exceeds its byte limit")
                    return bytes(data)
        except TimeoutError, httpx.HTTPError:
            raise VerificationUnavailable() from None

    async def prepare_element(self) -> None:
        if not self._context.root_execution_id or not self._context.execution_id:
            raise ValueError("Verification access requires execution identity")
        credential = self._credential
        if credential is None and self._source is not None:
            try:
                credential = await self._source.resolve(
                    "verification@1", self._context.identity, self._context.root_execution_id
                )
            except WorkflowCredentialUnavailable:
                raise VerificationUnavailable() from None
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
        content = await self._request("GET", "/api/verification-access/self")
        try:
            grant = VerificationAccessGrant.model_validate_json(content)
        except ValidationError:
            raise ValueError("Verification grant violates its contract") from None
        if (
            not grant.owner.owns(self._context.identity)
            or grant.scope.root_execution_id != self._context.root_execution_id
        ):
            raise VerificationCredentialError(
                "Verification credential does not match this execution"
            )
        self._grant = grant

    def _view(self, content: bytes) -> VerificationView:
        try:
            view = VerificationView.model_validate_json(content)
        except ValidationError:
            raise ValueError("Verification response violates its contract") from None
        if (
            self._grant is None
            or not view.state.plan.owner.owns(self._grant.owner)
            or view.state.plan.root_execution_id != self._grant.scope.root_execution_id
            or view.state.plan.policy not in self._grant.scope.policies
        ):
            raise VerificationCredentialError("Verification response exceeds its scope")
        return view

    async def start(self, request: StartVerification) -> VerificationView:
        view = self._view(
            await self._request("POST", "/api/verifications", request.model_dump_json().encode())
        )
        if (
            view.state.plan.key != request.key
            or view.state.plan.policy != request.policy
            or view.state.plan.subject.fingerprint != request.subject.fingerprint
        ):
            raise ValueError("Verification response identifies different work")
        return view

    async def inspect(self, plan_id: str) -> VerificationView:
        view = self._view(await self._request("GET", "/api/verifications/" + plan_id))
        if view.state.plan.plan_id != plan_id:
            raise ValueError("Verification response identifies a different plan")
        return view

    async def cancel(self, plan_id: str) -> VerificationView:
        view = self._view(await self._request("POST", "/api/verifications/" + plan_id + "/cancel"))
        if view.state.plan.plan_id != plan_id:
            raise ValueError("Verification response identifies a different plan")
        return view

    def _check(self, content: bytes) -> CheckRun:
        try:
            run = CheckRun.model_validate_json(content)
        except ValidationError:
            raise ValueError("Check response violates its contract") from None
        if (
            self._grant is None
            or not run.plan.owner.owns(self._grant.owner)
            or run.plan.root_execution_id != self._grant.scope.root_execution_id
            or run.plan.policy not in self._grant.scope.policies
        ):
            raise VerificationCredentialError("Check response exceeds its scope")
        return run

    async def start_check(self, request: StartCheckRun) -> CheckRun:
        run = self._check(
            await self._request(
                "POST", "/api/verification-checks", request.model_dump_json().encode()
            )
        )
        if run.plan.plan_id != request.plan_id or run.runner != request.runner:
            raise ValueError("Check response identifies different work")
        return run

    async def refresh_check(self, intent_id: str) -> CheckRun:
        run = self._check(
            await self._request("POST", "/api/verification-checks/" + intent_id + "/refresh")
        )
        if run.intent_id != intent_id:
            raise ValueError("Check response identifies a different intent")
        return run

    async def aclose(self) -> None:
        client, self._http = self._http, None
        if client is not None:
            await client.aclose()
