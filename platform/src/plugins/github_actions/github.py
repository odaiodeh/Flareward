"""Operator-owned GitHub Actions checks; tokens never enter receiver bundles."""

import asyncio

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationError,
)

from lumora.services.verification.check_ports import (
    CheckProviderUnavailable,
)
from lumora.services.verification.domain.check_runs import (
    CheckRun,
    CheckRunObservation,
    CheckRunStatus,
)
from lumora.services.verification.domain.models import CheckVerdict
from plugins.git.domain.repositories import GitCommitId, GitRevision
from plugins.github_actions.github_config import GitHubCheckConfiguration
from plugins.github_actions.github_http import GitHubActionsAPI


class GitHubRepository(BaseModel):
    model_config = ConfigDict(extra="ignore")
    full_name: str


class GitHubRun(BaseModel):
    """Only provider fields needed to identify the trusted workflow occurrence."""

    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    id: int = Field(gt=0)
    workflow_id: int = Field(gt=0)
    run_attempt: int = Field(ge=1)
    event: str
    display_title: str
    head_sha: GitCommitId
    status: str
    conclusion: str | None = None
    repository: GitHubRepository


class GitHubRunList(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    total_count: int = Field(ge=0)
    workflow_runs: list[GitHubRun] = Field(max_length=100)


class GitHubDispatch(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    workflow_run_id: int = Field(gt=0)


class GitHubActionsCheckRunner:
    def __init__(self, configuration: GitHubCheckConfiguration, client: httpx.AsyncClient) -> None:
        self._config = configuration
        self._api = GitHubActionsAPI(configuration, client)

    @property
    def configuration_digest(self) -> str:
        return self._config.digest

    def validate(self, run: CheckRun) -> None:
        try:
            revision = GitRevision.model_validate(run.plan.subject.identity)
        except ValidationError:
            raise ValueError("GitHub check requires an exact Git revision") from None
        if (
            run.plan.subject.kind != "git-revision@1"
            or revision.repository != self._config.source_repository
        ):
            raise PermissionError("GitHub check candidate repository is not permitted")

    async def submit(self, run: CheckRun) -> CheckRunObservation:
        self.validate(run)
        revision = GitRevision.model_validate(run.plan.subject.identity)
        content = await self._api.request(
            "POST",
            f"/actions/workflows/{self._config.workflow_id}/dispatches",
            body={
                "ref": self._config.workflow_ref,
                "return_run_details": True,
                "inputs": {
                    "lumora_intent": run.intent_id,
                    "lumora_plan": run.plan.plan_id,
                    "lumora_check": run.check,
                    "candidate_commit": revision.commit,
                },
            },
        )
        try:
            receipt = GitHubDispatch.model_validate_json(content)
        except ValidationError:
            raise CheckProviderUnavailable("GitHub dispatch response is invalid") from None
        # Persist the acknowledged ID before inspecting the run; a failed GET cannot lose it.
        return CheckRunObservation(
            external_id=self._external_id(receipt.workflow_run_id), status=CheckRunStatus.QUEUED
        )

    def _external_id(self, run_id: int) -> str:
        return f"github-actions:{self._config.repository}:{run_id}:1"

    @staticmethod
    def _title(run: CheckRun) -> str:
        revision = GitRevision.model_validate(run.plan.subject.identity)
        return f"lumora-{run.intent_id}-{revision.commit}"

    def _observation(self, data: GitHubRun, run: CheckRun) -> CheckRunObservation:
        if (
            data.workflow_id != self._config.workflow_id
            or data.run_attempt != 1
            or data.event != "workflow_dispatch"
            or data.display_title != self._title(run)
            or data.head_sha != self._config.workflow_commit
            or data.repository.full_name.lower() != self._config.repository.lower()
        ):
            raise CheckProviderUnavailable(
                "GitHub check provenance does not match the admitted workflow"
            )
        if data.status == "completed":
            if data.conclusion == "success":
                verdict = CheckVerdict.PASSED
            elif data.conclusion == "failure":
                verdict = CheckVerdict.FAILED
            else:
                verdict = CheckVerdict.ERROR
            return CheckRunObservation(
                external_id=self._external_id(data.id),
                status=CheckRunStatus.COMPLETED,
                verdict=verdict,
            )
        if data.status == "in_progress":
            status = CheckRunStatus.RUNNING
        elif data.status in {"queued", "requested", "waiting", "pending"}:
            status = CheckRunStatus.QUEUED
        else:
            raise CheckProviderUnavailable("GitHub check status is unsupported")
        return CheckRunObservation(external_id=self._external_id(data.id), status=status)

    async def reconcile(self, run: CheckRun) -> CheckRunObservation | None:
        try:
            async with asyncio.timeout(self._config.timeout_seconds):
                return await self._reconcile(run)
        except TimeoutError:
            raise CheckProviderUnavailable("GitHub reconciliation exceeded its deadline") from None

    async def _reconcile(self, run: CheckRun) -> CheckRunObservation | None:
        self.validate(run)
        try:
            if run.observation is not None:
                prefix = "github-actions:" + self._config.repository + ":"
                identifier = run.observation.external_id
                if not identifier.startswith(prefix) or not identifier.endswith(":1"):
                    raise CheckProviderUnavailable("GitHub check identity is invalid")
                number = identifier[len(prefix) : -2]
                if not number.isdecimal():
                    raise CheckProviderUnavailable("GitHub check identity is invalid")
                data = GitHubRun.model_validate_json(
                    await self._api.request("GET", "/actions/runs/" + number)
                )
                if str(data.id) != number:
                    raise CheckProviderUnavailable("GitHub returned another check run")
                return self._observation(data, run)
            matches: dict[int, GitHubRun] = {}
            for page in range(1, self._config.reconciliation_pages + 1):
                content = await self._api.request(
                    "GET",
                    f"/actions/workflows/{self._config.workflow_id}/runs",
                    params={
                        "event": "workflow_dispatch",
                        "created": ">=" + run.created_at.isoformat(),
                        "per_page": 100,
                        "page": page,
                    },
                )
                result = GitHubRunList.model_validate_json(content)
                for candidate in result.workflow_runs:
                    if candidate.display_title == self._title(run):
                        matches[candidate.id] = candidate
                if page * 100 >= result.total_count:
                    if len(matches) > 1:
                        raise CheckProviderUnavailable(
                            "Multiple GitHub runs identify the same dispatch"
                        )
                    return self._observation(next(iter(matches.values())), run) if matches else None
            # A truncated search cannot establish that a candidate is unique.
            raise CheckProviderUnavailable("GitHub reconciliation search exceeds its bound")
        except ValidationError:
            raise CheckProviderUnavailable("GitHub check response is invalid") from None
