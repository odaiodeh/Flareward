"""Freeze checks, admit trusted receipts and derive acceptance for one exact subject."""

import hashlib
import json
from collections.abc import Callable, Mapping
from datetime import UTC, datetime, timedelta
from functools import partial

from mas.application.artifacts.access_models import ArtifactActor
from mas.application.artifacts.service import ArtifactService
from mas.application.verification.access_models import VerificationAction, VerificationActor
from mas.application.verification.models import (
    StartVerification,
    SubmitCheckEvidence,
    VerificationAuthority,
    VerificationPolicy,
    VerificationView,
)
from mas.application.verification.ports import (
    VerificationConflict,
    VerificationMissing,
    VerificationRepository,
)
from mas.domain.verification import (
    CheckEvidence,
    VerificationOutcome,
    VerificationPlan,
    VerificationState,
)


class VerificationService:
    def __init__(
        self,
        repository: VerificationRepository,
        policies: Mapping[str, VerificationPolicy],
        *,
        clock: Callable[[], datetime] | None = None,
        artifacts: ArtifactService | None = None,
    ) -> None:
        self._repository = repository
        self._policies = {key: policy.model_copy(deep=True) for key, policy in policies.items()}
        self._now = clock or partial(datetime.now, UTC)
        self._artifacts = artifacts

    async def start(self, request: StartVerification, actor: VerificationActor) -> VerificationView:
        owner, scope = actor.identity, actor.scope
        if scope is not None and not scope.allows(VerificationAction.CREATE, request.policy):
            raise PermissionError("Verification plan creation is not permitted")
        root = scope.root_execution_id if scope is not None else None
        if not owner.id:
            raise ValueError("Verification requires an owner identity")
        plan_id = hashlib.sha256(
            json.dumps(
                [owner.type.value, owner.id, root, request.key], separators=(",", ":")
            ).encode()
        ).hexdigest()
        existing = await self._repository.get(plan_id)
        if existing is None:
            policy = self._policies.get(request.policy)
            if policy is None or not any(identity.owns(owner) for identity in policy.owners):
                raise PermissionError("Verification policy is not permitted")
            if policy.subject_kind != request.subject.kind:
                raise ValueError("Verification policy does not support this subject kind")
            now = self._now()
            state = VerificationState(
                plan=VerificationPlan(
                    plan_id=plan_id,
                    owner=owner.model_copy(deep=True),
                    root_execution_id=root,
                    key=request.key,
                    subject=request.subject.model_copy(deep=True),
                    policy=request.policy,
                    requirements=policy.requirements,
                    created_at=now,
                    expires_at=now + timedelta(seconds=policy.timeout_seconds),
                )
            )
            if await self._repository.create(state):
                return self._view(state)
            existing = await self._get(plan_id)
        if (
            not existing.plan.owner.owns(owner)
            or existing.plan.subject.fingerprint != request.subject.fingerprint
            or existing.plan.policy != request.policy
        ):
            raise VerificationConflict("Verification intent already identifies different work")
        return self._view(existing)

    async def inspect(self, plan_id: str, actor: VerificationActor) -> VerificationView:
        state = await self._owned(plan_id, actor, VerificationAction.READ)
        return self._view(state)

    async def submit(
        self, request: SubmitCheckEvidence, authority: VerificationAuthority
    ) -> VerificationView:
        for _ in range(64):
            state = await self._get(request.plan_id)
            if not any(owner.owns(state.plan.owner) for owner in authority.owners):
                raise VerificationMissing("Verification not found")
            expected = next(
                (item for item in state.plan.requirements if item.check == request.check), None
            )
            if expected is None or authority.verifier not in expected.verifiers:
                raise PermissionError("Verifier is not permitted for this check")
            if state.plan.subject.fingerprint != request.subject.fingerprint:
                raise VerificationConflict("Evidence identifies a different candidate")
            existing = next((item for item in state.evidence if item.check == request.check), None)
            if existing is not None:
                if (
                    existing.verifier != authority.verifier
                    or existing.run_id != request.run_id
                    or existing.verdict != request.verdict
                    or existing.configuration_digest != request.configuration_digest
                    or existing.reports != request.reports
                ):
                    raise VerificationConflict("Check already has different immutable evidence")
                return self._view(state)
            now = self._now()
            if state.cancelled or now >= state.plan.expires_at:
                raise VerificationConflict("Verification no longer accepts evidence")
            if expected.requires_reports and not request.reports:
                raise VerificationConflict("Verification check requires durable reports")
            for report in request.reports:
                if self._artifacts is None:
                    raise ValueError("Verification report storage is not configured")
                record = await self._artifacts.inspect(
                    report.content.artifact_id, ArtifactActor(state.plan.owner)
                )
                if record.reference != report.content:
                    raise VerificationConflict("Evidence report does not match stored content")
            now = self._now()
            if now >= state.plan.expires_at:
                raise VerificationConflict("Verification no longer accepts evidence")
            receipt = CheckEvidence(
                check=request.check,
                verifier=authority.verifier,
                subject_fingerprint=state.plan.subject.fingerprint,
                run_id=request.run_id,
                verdict=request.verdict,
                recorded_at=now,
                configuration_digest=request.configuration_digest,
                reports=request.reports,
            )
            updated = state.model_copy(
                update={"evidence": (*state.evidence, receipt), "revision": state.revision + 1}
            )
            if await self._repository.save(updated, expected_revision=state.revision):
                return self._view(updated)
        raise VerificationConflict("Verification changed concurrently; retry the same intent")

    async def cancel(self, plan_id: str, actor: VerificationActor) -> VerificationView:
        for _ in range(64):
            state = await self._owned(plan_id, actor, VerificationAction.CANCEL)
            if state.cancelled:
                return self._view(state)
            if (
                len(state.evidence) == len(state.plan.requirements)
                or self._now() >= state.plan.expires_at
            ):
                raise VerificationConflict("Verification is already terminal")
            updated = state.model_copy(update={"cancelled": True, "revision": state.revision + 1})
            if await self._repository.save(updated, expected_revision=state.revision):
                return self._view(updated)
        raise VerificationConflict("Verification changed concurrently; retry cancellation")

    async def _get(self, plan_id: str) -> VerificationState:
        state = await self._repository.get(plan_id)
        if state is None:
            raise VerificationMissing("Verification not found")
        return state

    async def _owned(
        self, plan_id: str, actor: VerificationActor, action: VerificationAction
    ) -> VerificationState:
        if actor.scope is not None and action not in actor.scope.actions:
            raise PermissionError("Verification action is not permitted")
        state = await self._get(plan_id)
        if not state.plan.owner.owns(actor.identity) or (
            actor.scope is not None
            and (
                state.plan.root_execution_id != actor.scope.root_execution_id
                or not actor.scope.allows(action, state.plan.policy)
            )
        ):
            raise VerificationMissing("Verification not found")
        return state

    def _view(self, state: VerificationState) -> VerificationView:
        outcome = state.evidence_outcome
        if outcome is None:
            outcome = (
                VerificationOutcome.EXPIRED
                if self._now() >= state.plan.expires_at
                else VerificationOutcome.PENDING
            )
        return VerificationView(state=state, outcome=outcome)
