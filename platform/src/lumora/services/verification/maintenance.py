"""Retire owned check jobs through existing application cancellation and upkeep."""

import asyncio
import logging
from collections.abc import Mapping

from lumora.services.access.executions import ExecutionAccessUnavailable, ExecutionGrantAuthority
from lumora.services.verification.access_models import VerificationActor
from lumora.services.verification.check_ports import CheckProviderUnavailable, CheckRunRepository
from lumora.services.verification.check_service import RegisteredCheckRunner
from lumora.services.verification.domain.check_runs import (
    CheckJobState,
    CheckRun,
    CheckRunStatus,
)
from lumora.services.verification.domain.models import VerificationOutcome
from lumora.services.verification.ports import (
    VerificationConflict,
    VerificationMissing,
    VerificationStorageError,
)
from lumora.services.verification.service import VerificationService

logger = logging.getLogger(__name__)


class CheckJobMaintenance:
    def __init__(
        self,
        repository: CheckRunRepository,
        verification: VerificationService,
        runners: Mapping[str, RegisteredCheckRunner],
        roots: ExecutionGrantAuthority,
    ) -> None:
        self._repository, self._verification = repository, verification
        self._runners, self._roots = dict(runners), roots
        self._after = ""

    async def _retire(self, run: CheckRun) -> None:
        if run.job_state == CheckJobState.ACTIVE:
            actor = VerificationActor(run.plan.owner)
            view = await self._verification.inspect(run.plan.plan_id, actor)
            closed_root = (
                view.outcome == VerificationOutcome.PENDING
                and not run.evidence_recorded
                and bool(run.plan.root_execution_id)
                and await self._roots.closed(run.plan.root_execution_id or "", run.plan.owner)
            )
            if view.outcome == VerificationOutcome.PENDING and closed_root:
                try:
                    view = await self._verification.cancel(run.plan.plan_id, actor)
                except VerificationConflict:
                    view = await self._verification.inspect(run.plan.plan_id, actor)
            recorded = run.evidence_recorded or any(
                run.matches_receipt(receipt) for receipt in view.state.evidence
            )
            if view.outcome == VerificationOutcome.PENDING and not closed_root and not recorded:
                return
            target = (
                CheckJobState.CLOSED
                if run.status in {CheckRunStatus.READY, CheckRunStatus.REJECTED}
                else CheckJobState.RETIRING
            )
            updated = run.model_copy(update={"job_state": target, "revision": run.revision + 1})
            if recorded:
                updated = updated.model_copy(update={"evidence_recorded": True})
            if not await self._repository.save(updated, expected_revision=run.revision):
                return
            run = updated
        if run.job_state != CheckJobState.RETIRING:
            return
        registered = self._runners.get(run.runner)
        if (
            registered is None
            or registered.lifecycle is None
            or registered.driver.configuration_digest != run.configuration_digest
            or registered.policy.verifier != run.verifier
        ):
            raise CheckProviderUnavailable("Admitted verifier job binding is unavailable")
        if await registered.lifecycle.stop(run):
            updated = run.model_copy(
                update={"job_state": CheckJobState.CLOSED, "revision": run.revision + 1}
            )
            await self._repository.save(updated, expected_revision=run.revision)

    async def reconcile(self, limit: int = 20) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("Check maintenance page size must be between 1 and 100")
        runs = await self._repository.pending_jobs(after=self._after, limit=limit)
        if not runs:
            self._after = ""
            return
        deadline = asyncio.get_running_loop().time() + 5
        for run in runs:
            if asyncio.get_running_loop().time() >= deadline:
                return
            self._after = run.intent_id
            try:
                async with asyncio.timeout_at(deadline):
                    await self._retire(run)
            except (
                TimeoutError,
                CheckProviderUnavailable,
                ExecutionAccessUnavailable,
                VerificationConflict,
                VerificationMissing,
                VerificationStorageError,
            ):
                logger.warning("Verifier job maintenance remains pending")
