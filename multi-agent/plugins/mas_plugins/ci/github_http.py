"""Bounded authenticated GitHub API calls, separate from run and report semantics."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mas.application.verification.check_ports import (
    CheckProviderUnavailable,
    CheckSubmissionRejected,
)
from mas.domain.artifacts import ContentIdentity
from pydantic import JsonValue

from .github_config import GitHubCheckConfiguration


class GitHubActionsAPI:
    def __init__(self, configuration: GitHubCheckConfiguration, client: httpx.AsyncClient) -> None:
        self._config, self._http = configuration, client

    async def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, JsonValue] | None = None,
        params: dict[str, str | int] | None = None,
    ) -> bytes:
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                async with self._http.stream(
                    method,
                    "https://api.github.com/repos/" + self._config.repository + path,
                    headers={
                        "Authorization": "Bearer " + self._config.token.get_secret_value(),
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    json=body,
                    params=params,
                ) as response:
                    if method == "POST" and response.status_code in {400, 401, 403, 404, 422}:
                        raise CheckSubmissionRejected("GitHub refused the check dispatch")
                    if response.status_code != 200:
                        raise CheckProviderUnavailable(
                            "GitHub check acknowledgement is unavailable"
                        )
                    content = bytearray()
                    async for chunk in response.aiter_bytes():
                        content.extend(chunk)
                        if len(content) > 2_097_152:
                            raise CheckProviderUnavailable(
                                "GitHub check response exceeds its bound"
                            )
                    return bytes(content)
        except TimeoutError, httpx.HTTPError:
            raise CheckProviderUnavailable("GitHub check response is unavailable") from None

    @asynccontextmanager
    async def archive(
        self, artifact_id: int, identity: ContentIdentity
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        if identity.size_bytes > self._config.report_max_bytes:
            raise CheckProviderUnavailable("GitHub report exceeds its admitted byte limit")
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                async with self._http.stream(
                    "GET",
                    f"https://api.github.com/repos/{self._config.repository}/actions/artifacts/{artifact_id}/zip",
                    headers={
                        "Authorization": "Bearer " + self._config.token.get_secret_value(),
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    },
                    follow_redirects=False,
                ) as redirect:
                    if redirect.status_code != 302:
                        raise CheckProviderUnavailable("GitHub report download is unavailable")
                    location = httpx.URL(redirect.headers.get("Location", ""))
                if (
                    location.scheme != "https"
                    or location.username
                    or location.password
                    or location.fragment
                    or location.port not in (None, 443)
                    or not self._allowed_archive_host(location.host)
                ):
                    raise CheckProviderUnavailable("GitHub report download origin is not permitted")
                # Construct a fresh request: never forward API authentication, cookies,
                # inherited client auth or provider response headers to the archive host.
                request = httpx.Request("GET", location, headers={"Accept-Encoding": "identity"})
                response = await self._http.send(
                    request, auth=None, follow_redirects=False, stream=True
                )
                try:
                    if (
                        response.status_code != 200
                        or response.headers.get("Content-Encoding", "identity") != "identity"
                    ):
                        raise CheckProviderUnavailable("GitHub report content is unavailable")
                    yield self._chunks(response, identity.size_bytes)
                finally:
                    await response.aclose()
        except TimeoutError, httpx.HTTPError, httpx.InvalidURL:
            raise CheckProviderUnavailable("GitHub report transfer is unavailable") from None

    def _allowed_archive_host(self, host: str) -> bool:
        return any(
            host == pattern
            if not pattern.startswith("*.")
            else host.endswith(pattern[1:]) and host != pattern[2:]
            for pattern in self._config.archive_hosts
        )

    @staticmethod
    async def _chunks(response: httpx.Response, expected_size: int) -> AsyncIterator[bytes]:
        size = 0
        async for chunk in response.aiter_raw():
            size += len(chunk)
            if size > expected_size:
                raise CheckProviderUnavailable("GitHub report exceeds its recorded size")
            yield chunk
        if size != expected_size:
            raise CheckProviderUnavailable("GitHub report size does not match")
