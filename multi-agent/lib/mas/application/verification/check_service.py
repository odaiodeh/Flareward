"""Reserve dispatch once, reconcile uncertainty and attest trusted check outcomes."""

import hashlib
import json
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from functools import partial

from mas.application.verification.access_models import VerificationAction, VerificationActor
from mas.application.verification.check_ports import (
    CheckJobControl,
    CheckProviderUnavailable,
    CheckReports,
    CheckRunner,
    CheckRunnerPolicy,
    CheckRunRepository,
    CheckSubmissionRejected,
    ResolveCheckRun,
    StartCheckRun,
)
from mas.application.verification.models import SubmitCheckEvidence, VerificationAuthority
from mas.application.verification.ports import VerificationConflict, VerificationMissing
from mas.application.verification.reports import CheckReportCollector
from mas.application.verification.service import VerificationService
from mas.core.identity import Identity
from mas.domain.check_runs import (
    CheckJobState,
    CheckRun,
    CheckRunObservation,
    CheckRunResolution,
    CheckRunStatus,
)
from mas.domain.verification import VerificationOutcome


@dataclass(frozen=True)
class RegisteredCheckRunner:
    policy: CheckRunnerPolicy
    driver: CheckRunner
    reports: CheckReports | None = None
    lifecycle: CheckJobControl | None = None


class CheckRunService:
    def __init__(
        self,
        repository: CheckRunRepository,
        verification: VerificationService,
        runners: Mapping[str, RegisteredCheckRunner],
        *,
        clock: Callable[[], datetime] | None = None,
        reports: CheckReportCollector | None = None,
    ) -> None:
        self._repository, self._verification = repository, verification
        self._runners = dict(runners)
        self._now = clock or partial(datetime.now, UTC)
        self._reports = reports
        if any(item.reports is not None for item in self._runners.values()) and reports is None:
            raise ValueError("Configured check reports require durable artifact storage")

    @staticmethod
    def _authorize(actor: VerificationActor, policy: str) -> None:
        if actor.scope is not None and not actor.scope.allows(VerificationAction.RUN_CHECK, policy):
            raise PermissionError("Check execution is not permitted")

    async def start(self, request: StartCheckRun, actor: VerificationActor) -> CheckRun:
        view = await self._verification.inspect(request.plan_id, actor)
        plan = view.state.plan
        self._authorize(actor, plan.policy)
        registered = self._runners.get(request.runner)
        if registered is None:
            raise PermissionError("Check runner is not permitted")
        policy, driver = registered.policy, registered.driver
        if (
            not any(owner.owns(plan.owner) for owner in policy.owners)
            or plan.policy not in policy.policies
            or plan.subject.kind != policy.subject_kind
        ):
            raise PermissionError("Check runner is not permitted for this verification")
        requirement = next((item for item in plan.requirements if item.check == policy.check), None)
        if (
            requirement is None
            or policy.verifier not in requirement.verifiers
            or (requirement.requires_reports and registered.reports is None)
        ):
            raise PermissionError("Check runner does not satisfy this verification requirement")
        intent_id = hashlib.sha256(
            json.dumps([plan.plan_id, policy.check], separators=(",", ":")).encode()
        ).hexdigest()
        run = await self._repository.get(intent_id)
        if run is None:
            if view.outcome != VerificationOutcome.PENDING or any(
                evidence.check == policy.check for evidence in view.state.evidence
            ):
                raise VerificationConflict("Verification no longer admits this check")
            run = CheckRun(
                intent_id=intent_id,
                plan=plan,
                check=policy.check,
                runner=request.runner,
                verifier=policy.verifier,
                configuration_digest=driver.configuration_digest,
                created_at=self._now(),
                job_state=CheckJobState.ACTIVE if registered.lifecycle is not None else None,
            )
            driver.validate(run)
            if not await self._repository.create(run):
                run = await self._get(intent_id)
        if run.runner != request.runner:
            raise VerificationConflict("Check already identifies another runner")
        self._driver(run)
        if run.job_state in {CheckJobState.RETIRING, CheckJobState.CLOSED}:
            return run
        if run.status != CheckRunStatus.READY:
            return await self.refresh(intent_id, actor)
        if view.outcome != VerificationOutcome.PENDING or self._now() >= plan.expires_at:
            raise VerificationConflict("Verification no longer admits check submission")
        # Persist uncertainty BEFORE the POST. Only the winning revision may submit.
        claimed = run.model_copy(
            update={"status": CheckRunStatus.UNCERTAIN, "revision": run.revision + 1}
        )
        if not await self._repository.save(claimed, expected_revision=run.revision):
            return await self.refresh(intent_id, actor)
        try:
            observation = await driver.submit(claimed)
        except CheckSubmissionRejected:
            return await self._observe(claimed, None, rejected=True)
        except CheckProviderUnavailable:
            return claimed
        # Cancellation/process death leaves durable UNCERTAIN and never grants a retry POST.
        return await self._observe(claimed, observation)

    async def refresh(self, intent_id: str, actor: VerificationActor) -> CheckRun:
        run = await self._get(intent_id)
        await self._verification.inspect(run.plan.plan_id, actor)
        self._authorize(actor, run.plan.policy)
        driver = self._driver(run)
        if run.job_state in {CheckJobState.RETIRING, CheckJobState.CLOSED}:
            return run
        if run.status in {CheckRunStatus.READY, CheckRunStatus.REJECTED}:
            return run
        if run.status != CheckRunStatus.COMPLETED:
            try:
                observation = await driver.reconcile(run)
            except CheckProviderUnavailable:
                return run
            if observation is None:
                return run
            run = await self._observe(run, observation)
        if run.job_state in {CheckJobState.RETIRING, CheckJobState.CLOSED}:
            return run
        if run.status == CheckRunStatus.COMPLETED and not run.evidence_recorded:
            run = await self._collect(run)
            if run.job_state in {CheckJobState.RETIRING, CheckJobState.CLOSED}:
                return run
            assert run.observation is not None and run.observation.verdict is not None
            await self._verification.submit(
                SubmitCheckEvidence(
                    plan_id=run.plan.plan_id,
                    subject=run.plan.subject,
                    check=run.check,
                    run_id=run.observation.external_id,
                    verdict=run.observation.verdict,
                    reports=run.reports,
                    configuration_digest=run.configuration_digest,
                ),
                VerificationAuthority(verifier=run.verifier, owners=(run.plan.owner,)),
            )
            # If this acknowledgement is lost, the immutable evidence API deduplicates it.
            updated = run.model_copy(
                update={"evidence_recorded": True, "revision": run.revision + 1}
            )
            await self._repository.save(updated, expected_revision=run.revision)
            return await self._get(intent_id)
        return run

    async def inspect(self, intent_id: str, actor: VerificationActor) -> CheckRun:
        run = await self._get(intent_id)
        await self._verification.inspect(run.plan.plan_id, actor)
        return run

    async def resolve(
        self, intent_id: str, request: ResolveCheckRun, owner: Identity, issued_by: Identity
    ) -> CheckRun:
        if (
            not issued_by.is_user
            or not issued_by.id
            or (owner.is_user and not owner.owns(issued_by))
        ):
            raise PermissionError("Check resolution requires authenticated human authority")
        run = await self._get(intent_id)
        await self._verification.inspect(run.plan.plan_id, VerificationActor(owner))
        if run.resolution is not None:
            previous = run.resolution
            if self._same_resolution(previous, request, issued_by):
                return run
            raise VerificationConflict("Check already has a different resolution")
        if (
            run.revision != request.expected_revision
            or run.status != CheckRunStatus.UNCERTAIN
            or run.observation is not None
        ):
            raise VerificationConflict("Check resolution requires the current uncertain revision")
        candidate = run.model_copy(
            update={
                "observation": CheckRunObservation(
                    external_id=request.external_id, status=CheckRunStatus.QUEUED
                ),
                "status": CheckRunStatus.QUEUED,
            }
        )
        observation = await self._driver(run).reconcile(candidate)
        if observation is None or observation.external_id != request.external_id:
            raise VerificationConflict("Provider has not confirmed the proposed run")
        resolution = CheckRunResolution(
            key=request.key,
            external_id=request.external_id,
            reason=request.reason,
            issued_by=issued_by,
            recorded_at=self._now(),
        )
        updated = run.model_copy(
            update={
                "resolution": resolution,
                "observation": observation,
                "status": observation.status,
                "revision": run.revision + 1,
            }
        )
        if not await self._repository.save(updated, expected_revision=run.revision):
            # Same intent can acknowledge an accepted resolution; a different one conflicts.
            latest = await self._get(intent_id)
            if latest.resolution is not None and self._same_resolution(
                latest.resolution, request, issued_by
            ):
                return latest
            raise VerificationConflict(
                "Check changed during resolution; inspect the current revision"
            )
        return updated

    @staticmethod
    def _same_resolution(
        previous: CheckRunResolution, request: ResolveCheckRun, issued_by: Identity
    ) -> bool:
        return (
            previous.key == request.key
            and previous.external_id == request.external_id
            and previous.reason == request.reason
            and previous.issued_by.owns(issued_by)
        )

    async def _collect(self, run: CheckRun) -> CheckRun:
        for _ in range(64):
            if run.job_state in {CheckJobState.RETIRING, CheckJobState.CLOSED}:
                return run
            if run.reports_collected:
                return run
            provider = self._runners[run.runner].reports
            if run.report_sources is None:
                sources = await provider.list(run) if provider is not None else ()
                requirement = next(
                    item for item in run.plan.requirements if item.check == run.check
                )
                if requirement.requires_reports and not sources:
                    raise CheckProviderUnavailable("Verification check reports are not available")
                # Reconstruct at this portable-data boundary before admitting a manifest.
                updated = CheckRun.model_validate(
                    {**run.model_dump(), "report_sources": sources, "revision": run.revision + 1}
                )
            else:
                if run.report_sources:
                    if self._reports is None or provider is None:
                        raise VerificationConflict("Admitted check report provider is unavailable")
                    reports = await self._reports.collect(run, provider)
                else:
                    reports = ()
                updated = CheckRun.model_validate(
                    {
                        **run.model_dump(),
                        "reports": reports,
                        "reports_collected": True,
                        "revision": run.revision + 1,
                    }
                )
            if await self._repository.save(updated, expected_revision=run.revision):
                run = updated
            else:
                run = await self._get(run.intent_id)
        raise VerificationConflict("Check reports changed concurrently; retry inspection")

    def _driver(self, run: CheckRun) -> CheckRunner:
        registered = self._runners.get(run.runner)
        if registered is None or registered.driver.configuration_digest != run.configuration_digest:
            raise VerificationConflict(
                "Check runner configuration changed; restore the admitted binding"
            )
        if registered.policy.verifier != run.verifier:
            raise VerificationConflict("Check runner authority changed")
        return registered.driver

    async def _get(self, intent_id: str) -> CheckRun:
        run = await self._repository.get(intent_id)
        if run is None:
            raise VerificationMissing("Check run not found")
        return run

    async def _observe(
        self, run: CheckRun, observation: CheckRunObservation | None, *, rejected: bool = False
    ) -> CheckRun:
        for _ in range(64):
            if run.job_state in {CheckJobState.RETIRING, CheckJobState.CLOSED}:
                return run
            if run.status in {CheckRunStatus.COMPLETED, CheckRunStatus.REJECTED}:
                if observation is not None and (
                    run.observation is None
                    or run.observation.external_id != observation.external_id
                    or (
                        observation.status == CheckRunStatus.COMPLETED
                        and run.observation.verdict != observation.verdict
                    )
                ):
                    raise VerificationConflict(
                        "Check provider returned conflicting terminal evidence"
                    )
                return run
            previous = run.observation
            if previous is not None and (
                observation is None or previous.external_id != observation.external_id
            ):
                raise VerificationConflict("Check provider returned conflicting run identities")
            if (
                previous is not None
                and previous.status == CheckRunStatus.RUNNING
                and observation is not None
                and observation.status == CheckRunStatus.QUEUED
            ):
                return run
            updated = run.model_copy(
                update={
                    "status": CheckRunStatus.REJECTED
                    if rejected
                    else observation.status
                    if observation
                    else CheckRunStatus.UNCERTAIN,
                    "observation": observation,
                    "revision": run.revision + 1,
                }
            )
            if await self._repository.save(updated, expected_revision=run.revision):
                return updated
            run = await self._get(run.intent_id)
        raise VerificationConflict("Check observation changed concurrently; retry inspection")
