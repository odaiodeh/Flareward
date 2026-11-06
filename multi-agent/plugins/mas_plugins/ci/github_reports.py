"""Immutable GitHub report manifests and archive transfer, without acceptance policy."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import httpx
from mas.application.verification.check_ports import CheckProviderUnavailable
from mas.domain.artifacts import ContentIdentity
from mas.domain.check_runs import CheckRun, CheckRunStatus
from mas.domain.repositories import GitCommitId
from mas.domain.verification import CheckReportSource
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from .github import GitHubActionsCheckRunner
from .github_config import GitHubCheckConfiguration
from .github_http import GitHubActionsAPI


class GitHubArtifactRun(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    id: int = Field(gt=0)
    head_sha: GitCommitId


class GitHubArtifact(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    id: int = Field(gt=0)
    name: str = Field(min_length=1, max_length=255)
    size_in_bytes: int = Field(ge=0)
    digest: str = Field(pattern=r"^sha256:[a-f0-9]{64}$")
    expired: bool
    workflow_run: GitHubArtifactRun


class GitHubArtifactList(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    total_count: int = Field(ge=0)
    artifacts: tuple[GitHubArtifact, ...] = Field(max_length=100)


class GitHubCheckReports:
    def __init__(self, configuration: GitHubCheckConfiguration, client: httpx.AsyncClient) -> None:
        self._config = configuration
        self._api = GitHubActionsAPI(configuration, client)
        self._runs = GitHubActionsCheckRunner(configuration, client)

    def _number(self, run: CheckRun) -> str:
        if run.status != CheckRunStatus.COMPLETED or run.observation is None:
            raise ValueError("Check reports require a completed provider run")
        prefix = "github-actions:" + self._config.repository + ":"
        value = run.observation.external_id
        if (
            not value.startswith(prefix)
            or not value.endswith(":1")
            or not value[len(prefix) : -2].isdecimal()
        ):
            raise CheckProviderUnavailable("GitHub report run identity is invalid")
        return value[len(prefix) : -2]

    def _source(self, artifact: GitHubArtifact, run: CheckRun) -> CheckReportSource:
        if (
            artifact.expired
            or str(artifact.workflow_run.id) != self._number(run)
            or artifact.workflow_run.head_sha != self._config.workflow_commit
            or artifact.name not in self._config.report_names
            or artifact.size_in_bytes > self._config.report_max_bytes
        ):
            raise CheckProviderUnavailable(
                "GitHub report provenance does not match the admitted check"
            )
        return CheckReportSource(
            external_id=f"github-artifact:{self._config.repository}:{artifact.id}",
            name=artifact.name + ".zip",
            media_type="application/zip",
            identity=ContentIdentity(sha256=artifact.digest[7:], size_bytes=artifact.size_in_bytes),
        )

    async def list(self, run: CheckRun) -> tuple[CheckReportSource, ...]:
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                observed = await self._runs.reconcile(run)
                if observed != run.observation:
                    raise CheckProviderUnavailable("GitHub check changed before report admission")
                reports = []
                for name in self._config.report_names:
                    content = await self._api.request(
                        "GET",
                        f"/actions/runs/{self._number(run)}/artifacts",
                        params={"name": name, "per_page": 100},
                    )
                    result = GitHubArtifactList.model_validate_json(content)
                    if (
                        result.total_count != 1
                        or len(result.artifacts) != 1
                        or result.artifacts[0].name != name
                    ):
                        raise CheckProviderUnavailable(
                            "GitHub check report is missing or ambiguous"
                        )
                    reports.append(self._source(result.artifacts[0], run))
                return tuple(reports)
        except TimeoutError, ValidationError:
            raise CheckProviderUnavailable("GitHub check report manifest is unavailable") from None

    @asynccontextmanager
    async def open(
        self, run: CheckRun, source: CheckReportSource
    ) -> AsyncIterator[AsyncIterator[bytes]]:
        prefix = "github-artifact:" + self._config.repository + ":"
        identifier = source.external_id
        if not identifier.startswith(prefix) or not identifier[len(prefix) :].isdecimal():
            raise CheckProviderUnavailable("GitHub report identity is invalid")
        number = int(identifier[len(prefix) :])
        try:
            artifact = GitHubArtifact.model_validate_json(
                await self._api.request("GET", f"/actions/artifacts/{number}")
            )
        except ValidationError:
            raise CheckProviderUnavailable("GitHub report metadata is invalid") from None
        if artifact.id != number or self._source(artifact, run) != source:
            raise CheckProviderUnavailable("GitHub report changed after admission")
        async with self._api.archive(number, source.identity) as content:
            yield content
