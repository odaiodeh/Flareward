"""Report policy and immutable provenance depend on owned artifact ports, not storage adapters."""

from unittest.mock import create_autospec

import pytest
from mas.application.artifacts.ports import ArtifactMissing, ArtifactRepository
from mas.application.artifacts.service import ArtifactService
from mas.application.verification.access_models import VerificationActor
from mas.application.verification.models import SubmitCheckEvidence
from mas.application.verification.ports import VerificationConflict
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from mas.domain.artifacts import ArtifactRecord, BlobArtifactRef, ContentIdentity
from mas.domain.verification import (
    CheckReport,
    CheckReportSource,
    CheckVerdict,
    VerificationOutcome,
)
from support.check_runs import source_policy, source_request
from support.verification import (
    MemoryVerificationRepository,
    VerificationClock,
    verification_authority,
)


@pytest.fixture
async def evidence():
    owner, clock = Identity.user("owner"), VerificationClock()
    repository = create_autospec(ArtifactRepository, instance=True)
    report = CheckReport(
        source=CheckReportSource(
            external_id="ci:report:1",
            name="tests.json",
            identity=ContentIdentity(sha256="c" * 64, size_bytes=6),
        ),
        content=BlobArtifactRef(artifact_id="a" * 64, sha256="c" * 64, size_bytes=6),
    )
    record = ArtifactRecord(
        owner=owner,
        reference=report.content,
        namespace="verification-reports",
        name=report.source.name,
        media_type="application/json",
    )
    repository.get.return_value = record
    service = VerificationService(
        MemoryVerificationRepository(),
        {"source@1": source_policy(owner, requires_reports=True)},
        clock=clock,
        artifacts=ArtifactService(repository),
    )
    plan = (await service.start(source_request(), VerificationActor(owner))).state.plan
    request = SubmitCheckEvidence(
        plan_id=plan.plan_id,
        subject=plan.subject,
        check="tests@1",
        run_id="ci:1",
        verdict=CheckVerdict.PASSED,
        reports=(report,),
        configuration_digest="e" * 64,
    )
    return owner, service, repository, record, request, clock


async def test_policy_requires_reports_and_immutable_provenance_survives_duplicate_ack(evidence):
    owner, service, repository, _, request, _ = evidence
    authority = verification_authority(owner, "github-ci")
    with pytest.raises(VerificationConflict, match="requires durable reports"):
        await service.submit(request.model_copy(update={"reports": ()}), authority)
    accepted = await service.submit(request, authority)
    assert accepted.outcome == VerificationOutcome.ACCEPTED
    repository.get.reset_mock()
    assert await service.submit(request, authority) == accepted
    repository.get.assert_not_awaited()
    with pytest.raises(VerificationConflict):
        await service.submit(
            request.model_copy(update={"configuration_digest": "f" * 64}), authority
        )
    altered = request.reports[0].model_copy(
        update={
            "source": request.reports[0].source.model_copy(
                update={"external_id": "ci:another-report"}
            )
        }
    )
    with pytest.raises(VerificationConflict):
        await service.submit(request.model_copy(update={"reports": (altered,)}), authority)


async def test_foreign_report_bytes_cannot_satisfy_an_owned_plan(evidence):
    owner, service, repository, record, request, _ = evidence
    repository.get.return_value = record.model_copy(update={"owner": Identity.user("other")})
    with pytest.raises(ArtifactMissing):
        await service.submit(request, verification_authority(owner, "github-ci"))
    view = await service.inspect(request.plan_id, VerificationActor(owner))
    assert view.outcome == VerificationOutcome.PENDING and not view.state.evidence


async def test_report_authorization_cannot_admit_evidence_after_the_deadline(evidence):
    owner, service, repository, record, request, clock = evidence

    async def delayed_metadata(artifact_id):
        clock.advance(3601)
        return record

    repository.get.side_effect = delayed_metadata
    with pytest.raises(VerificationConflict, match="no longer accepts"):
        await service.submit(request, verification_authority(owner, "github-ci"))
    view = await service.inspect(request.plan_id, VerificationActor(owner))
    assert view.outcome == VerificationOutcome.EXPIRED and not view.state.evidence
