"""Provider provenance and actual durable bytes gate evidence, including partial recovery."""

from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from mas.application.artifacts.access_models import ArtifactActor
from mas.application.artifacts.ports import ArtifactIntegrityError
from mas.application.artifacts.service import ArtifactService
from mas.application.verification.access_models import VerificationActor
from mas.application.verification.check_ports import CheckProviderUnavailable, StartCheckRun
from mas.application.verification.check_service import CheckRunService, RegisteredCheckRunner
from mas.application.verification.ports import VerificationStorageError
from mas.application.verification.reports import CheckReportCollector
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from mas.domain.check_runs import CheckRun
from mas.domain.verification import VerificationOutcome
from mas_plugins.ci.github import GitHubActionsCheckRunner
from mas_plugins.ci.github_reports import GitHubCheckReports
from outbound.artifacts.filesystem import FileArtifactRepository
from support.check_runs import MemoryCheckRunRepository, source_policy, source_request
from support.github_checks import GitHubProtocol, github_configuration, report_archive
from support.verification import MemoryVerificationRepository, VerificationClock


@dataclass(frozen=True)
class ReportScenario:
    owner: Identity
    actor: VerificationActor
    run: CheckRun
    wire: GitHubProtocol
    records: MemoryCheckRunRepository
    checks: CheckRunService
    verification: VerificationService
    artifacts: ArtifactService
    directory: Path


@pytest.fixture
async def reports(tmp_path):
    owner, clock = Identity.user("owner"), VerificationClock()
    actor = VerificationActor(owner)
    artifacts = ArtifactService(FileArtifactRepository(tmp_path))
    verification = VerificationService(
        MemoryVerificationRepository(),
        {"source@1": source_policy(owner, requires_reports=True)},
        artifacts=artifacts,
        clock=clock,
    )
    plan = (await verification.start(source_request(), actor)).state.plan
    config, wire = github_configuration(owner, reports=True), GitHubProtocol(reports=True)
    records = MemoryCheckRunRepository()
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(wire),
        headers={
            "Authorization": "Bearer inherited-client-secret",
            "Cookie": "control-plane=private-cookie",
        },
    ) as http:
        checks = CheckRunService(
            records,
            verification,
            {
                "github@1": RegisteredCheckRunner(
                    config.policy,
                    GitHubActionsCheckRunner(config, http),
                    GitHubCheckReports(config, http),
                )
            },
            reports=CheckReportCollector(artifacts),
            clock=clock,
        )
        run = await checks.start(StartCheckRun(plan_id=plan.plan_id, runner="github@1"), actor)
        wire.complete()
        yield ReportScenario(
            owner, actor, run, wire, records, checks, verification, artifacts, tmp_path
        )


async def test_durable_report_bytes_and_provenance_survive_provider_retention(reports):
    case = reports
    completed = await case.checks.refresh(case.run.intent_id, case.actor)
    assert completed.reports_collected and completed.evidence_recorded
    view = await case.verification.inspect(completed.plan.plan_id, case.actor)
    assert view.outcome == VerificationOutcome.ACCEPTED
    evidence = view.state.evidence[0]
    assert evidence.configuration_digest == completed.configuration_digest
    assert evidence.reports == completed.reports and len(evidence.reports) == 1
    report = evidence.reports[0]
    assert report.source.external_id == "github-artifact:example/product:501"
    assert report.content.sha256 == report.source.identity.sha256
    # Byte access remains independent from ephemeral provider artifacts or process memory.
    case.wire.artifacts.clear()
    case.wire.runs.clear()
    restored = ArtifactService(FileArtifactRepository(case.directory))
    async with restored.open(report.content, ArtifactActor(case.owner)) as chunks:
        assert b"".join([chunk async for chunk in chunks]) == report_archive()
    assert await case.checks.refresh(case.run.intent_id, case.actor) == completed
    portable = completed.model_dump_json() + view.model_dump_json()
    assert all(
        secret not in portable
        for secret in (
            "private-test-github-token",
            "private-signed-url",
            "private-cookie",
            "inherited-client-secret",
        )
    )
    archive_request = next(
        request for request in case.wire.requests if request.url.host == "reports.example.test"
    )
    assert (
        "Authorization" not in archive_request.headers and "Cookie" not in archive_request.headers
    )


async def test_corrupt_report_bytes_never_satisfy_the_check_and_release_staging(reports):
    case = reports
    case.wire.archive = b"!" + case.wire.archive[1:]
    with pytest.raises(ArtifactIntegrityError):
        await case.checks.refresh(case.run.intent_id, case.actor)
    assert not (await case.checks.inspect(case.run.intent_id, case.actor)).evidence_recorded
    assert (
        await case.verification.inspect(case.run.plan.plan_id, case.actor)
    ).outcome == VerificationOutcome.PENDING
    assert not list(case.directory.glob(".upload-*"))
    assert not any(path.name[0] != "." for path in case.directory.iterdir())


@pytest.mark.parametrize(
    "case_name", ["missing", "duplicate", "expired", "wrong-run", "wrong-workflow", "oversized"]
)
async def test_missing_or_untrusted_report_manifest_cannot_attest(reports, case_name):
    case = reports
    artifact = case.wire.artifacts[0]
    if case_name == "missing":
        case.wire.artifacts.clear()
    elif case_name == "duplicate":
        case.wire.artifacts.append({**artifact, "id": 502})
    elif case_name == "expired":
        artifact["expired"] = True
    elif case_name == "wrong-run":
        artifact["workflow_run"]["id"] = 1002
    elif case_name == "wrong-workflow":
        artifact["workflow_run"]["head_sha"] = "d" * 40
    else:
        artifact["size_in_bytes"] = 16_777_217
    with pytest.raises(CheckProviderUnavailable):
        await case.checks.refresh(case.run.intent_id, case.actor)
    stored = await case.checks.inspect(case.run.intent_id, case.actor)
    assert stored.report_sources is None and not stored.evidence_recorded
    assert (
        await case.verification.inspect(stored.plan.plan_id, case.actor)
    ).outcome == VerificationOutcome.PENDING
    assert not any(request.url.host != "api.github.com" for request in case.wire.requests)


@pytest.mark.parametrize(
    "origin",
    [
        "https://attacker.example/archive",
        "http://reports.example.test/archive",
        "https://user:password@reports.example.test/archive",
        "https://reports.example.test:8443/archive",
    ],
)
async def test_archive_redirect_policy_prevents_unapproved_requests(reports, origin):
    case = reports
    case.wire.archive_location = origin
    with pytest.raises(CheckProviderUnavailable, match="origin"):
        await case.checks.refresh(case.run.intent_id, case.actor)
    assert not (await case.checks.inspect(case.run.intent_id, case.actor)).evidence_recorded
    assert all(request.url.host == "api.github.com" for request in case.wire.requests)


async def test_publication_acknowledgement_loss_recovers_without_redownloading_expired_source(
    reports,
):
    case = reports
    case.records.fail_report_acknowledgement = True
    with pytest.raises(VerificationStorageError):
        await case.checks.refresh(case.run.intent_id, case.actor)
    stored = await case.checks.inspect(case.run.intent_id, case.actor)
    assert stored.report_sources is not None and not stored.reports_collected
    assert (
        await case.verification.inspect(stored.plan.plan_id, case.actor)
    ).outcome == VerificationOutcome.PENDING
    requests = len(case.wire.requests)
    case.wire.artifacts.clear()
    case.records.fail_report_acknowledgement = False
    recovered = await case.checks.refresh(case.run.intent_id, case.actor)
    assert recovered.evidence_recorded and recovered.reports_collected
    assert len(case.wire.requests) == requests
    assert case.wire.submissions == 1
