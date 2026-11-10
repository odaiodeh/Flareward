"""Deterministic GitHub wire fixture, not evidence of a live GitHub-hosted job."""

import hashlib
import json
from io import BytesIO
from zipfile import ZipFile, ZipInfo

import httpx

from lumora.services.identity.domain import Identity
from plugins.github_actions.github_config import GitHubCheckConfiguration
from support.check_runs import check_policy


def report_archive() -> bytes:
    destination = BytesIO()
    with ZipFile(destination, "w") as archive:
        archive.writestr(
            ZipInfo("report.json", date_time=(2026, 11, 3, 0, 0, 0)),
            json.dumps({"candidate_commit": "b" * 40, "tests": 3, "failed": 0}),
        )
    return destination.getvalue()


def github_configuration(owner: Identity, *, reports: bool = False) -> GitHubCheckConfiguration:
    return GitHubCheckConfiguration(
        policy=check_policy(owner),
        repository="example/product",
        source_repository="product",
        workflow_id=42,
        workflow_ref="checks-v1",
        workflow_commit="c" * 40,
        token="private-test-github-token",
        report_names=("test-results",) if reports else (),
        archive_hosts=frozenset({"reports.example.test"}) if reports else frozenset(),
    )


class GitHubProtocol:
    def __init__(self, *, lose_acknowledgement: bool = False, reports: bool = False) -> None:
        self.lose_acknowledgement = lose_acknowledgement
        self.requests: list[httpx.Request] = []
        self.runs: list[dict] = []
        self.post_status = 200
        self.total_count: int | None = None
        self.archive = report_archive()
        self.archive_location = "https://reports.example.test/archive?signature=private-signed-url"
        self.artifacts = (
            [
                {
                    "id": 501,
                    "name": "test-results",
                    "size_in_bytes": len(self.archive),
                    "digest": "sha256:" + hashlib.sha256(self.archive).hexdigest(),
                    "expired": False,
                    "workflow_run": {"id": 1001, "head_sha": "c" * 40},
                }
            ]
            if reports
            else []
        )

    @property
    def submissions(self) -> int:
        return sum(request.method == "POST" for request in self.requests)

    def complete(self, conclusion: str = "success") -> None:
        self.runs[0].update(status="completed", conclusion=conclusion)

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if request.url.host == "reports.example.test":
            assert "Authorization" not in request.headers and "Cookie" not in request.headers
            return httpx.Response(200, stream=httpx.ByteStream(self.archive))
        assert request.url.host == "api.github.com"
        assert request.headers["Authorization"] == "Bearer private-test-github-token"
        assert request.headers["X-GitHub-Api-Version"] == "2022-11-28"
        if request.method == "POST":
            if self.post_status != 200:
                return httpx.Response(self.post_status, text="private provider diagnostic")
            body = json.loads(request.content)
            assert body["ref"] == "checks-v1" and body["return_run_details"] is True
            assert body["inputs"]["candidate_commit"] == "b" * 40
            assert set(body["inputs"]) == {
                "lumora_intent",
                "lumora_plan",
                "lumora_check",
                "candidate_commit",
            }
            self.runs.append(
                {
                    "id": 1001,
                    "workflow_id": 42,
                    "run_attempt": 1,
                    "event": "workflow_dispatch",
                    "display_title": "lumora-"
                    + body["inputs"]["lumora_intent"]
                    + "-"
                    + body["inputs"]["candidate_commit"],
                    "head_sha": "c" * 40,
                    "status": "queued",
                    "conclusion": None,
                    "repository": {"full_name": "example/product", "ignored_field": "value"},
                }
            )
            if self.lose_acknowledgement:
                raise httpx.ReadError("private lost acknowledgement", request=request)
            return httpx.Response(200, json={"workflow_run_id": 1001})
        if request.url.path.endswith("/artifacts"):
            return httpx.Response(
                200, json={"total_count": len(self.artifacts), "artifacts": self.artifacts}
            )
        if "/actions/artifacts/" in request.url.path:
            if request.url.path.endswith("/zip"):
                return httpx.Response(302, headers={"Location": self.archive_location})
            if not self.artifacts:
                return httpx.Response(410)
            return httpx.Response(200, json=self.artifacts[0])
        if request.url.path.endswith("/runs"):
            return httpx.Response(
                200,
                json={
                    "total_count": len(self.runs) if self.total_count is None else self.total_count,
                    "workflow_runs": self.runs,
                },
            )
        return httpx.Response(200, json=self.runs[0])
