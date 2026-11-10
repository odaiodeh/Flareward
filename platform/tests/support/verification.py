"""Shared verification policies and application-owned persistence/clock doubles."""

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from lumora.services.identity.domain import Identity
from lumora.services.verification.access_models import StoredVerificationAccess
from lumora.services.verification.domain.models import (
    CheckRequirement,
    CheckVerdict,
    VerificationState,
    VerificationSubject,
)
from lumora.services.verification.models import (
    StartVerification,
    SubmitCheckEvidence,
    VerificationAuthority,
    VerificationPolicy,
)


@dataclass
class VerificationClock:
    now: datetime = datetime(2026, 11, 1, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: int) -> None:
        self.now += timedelta(seconds=seconds)


class MemoryVerificationRepository:
    def __init__(self) -> None:
        self._states: dict[str, VerificationState] = {}

    async def create(self, state: VerificationState) -> bool:
        if state.plan.plan_id in self._states:
            return False
        self._states[state.plan.plan_id] = state.model_copy(deep=True)
        return True

    async def get(self, plan_id: str) -> VerificationState | None:
        await asyncio.sleep(0)
        state = self._states.get(plan_id)
        return state.model_copy(deep=True) if state else None

    async def save(self, state: VerificationState, *, expected_revision: int) -> bool:
        await asyncio.sleep(0)
        existing = self._states.get(state.plan.plan_id)
        if existing is None or existing.revision != expected_revision:
            return False
        self._states[state.plan.plan_id] = state.model_copy(deep=True)
        return True


class MemoryVerificationAccessRepository:
    def __init__(self) -> None:
        self.records: dict[str, StoredVerificationAccess] = {}

    async def create(self, access: StoredVerificationAccess) -> None:
        self.records[access.grant.grant_id] = access.model_copy(deep=True)

    async def ensure(self, access: StoredVerificationAccess) -> StoredVerificationAccess:
        return self.records.setdefault(access.grant.grant_id, access).model_copy(deep=True)

    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredVerificationAccess | None:
        record = self.records.get(grant_id)
        if (
            record is not None
            and active_at is not None
            and (record.grant.revoked or record.grant.expires_at <= active_at)
        ):
            return None
        return record.model_copy(deep=True) if record else None

    async def list(
        self, owner: Identity, *, after: str, limit: int
    ) -> list[StoredVerificationAccess]:
        return [
            record.model_copy(deep=True)
            for key, record in sorted(self.records.items())
            if key > after and record.grant.owner.owns(owner)
        ][:limit]

    async def revoke(self, grant_id: str) -> None:
        record = self.records[grant_id]
        self.records[grant_id] = record.model_copy(
            update={"grant": record.grant.model_copy(update={"revoked": True})}
        )

    async def pending(self, *, after: str, limit: int) -> Sequence[StoredVerificationAccess]:
        return [
            stored
            for key, stored in sorted(self.records.items())
            if key > after and not stored.grant.revoked
        ][:limit]

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool:
        current = self.records[grant_id]
        if (
            current.grant.revoked
            or current.grant.expires_at != expected_expiry
            or expected_expiry > now
        ):
            return False
        await self.revoke(grant_id)
        return True

    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool:
        current = self.records[grant_id]
        grant = current.grant
        if (
            grant.revoked
            or grant.expires_at != expected_expiry
            or grant.renewal is None
            or grant.renewal.next_expiry(now, expected_expiry) != expires_at
        ):
            return False
        self.records[grant_id] = current.model_copy(
            update={"grant": grant.model_copy(update={"expires_at": expires_at})}
        )
        return True


def verification_policy(owner: Identity) -> VerificationPolicy:
    return VerificationPolicy(
        owners=(owner,),
        subject_kind="build-image@1",
        requirements=(
            CheckRequirement(check="tests@1", verifiers=frozenset({"ci"})),
            CheckRequirement(check="security@1", verifiers=frozenset({"scanner"})),
        ),
        timeout_seconds=60,
    )


def verification_request(key: str = "work", digest: str = "a" * 64) -> StartVerification:
    return StartVerification(
        key=key,
        policy="release@1",
        subject=VerificationSubject(
            kind="build-image@1", identity={"image": "product", "digest": "sha256:" + digest}
        ),
    )


def evidence_request(plan, check="tests@1", verdict=CheckVerdict.PASSED, run_id="ci-run"):
    return SubmitCheckEvidence(
        plan_id=plan.plan_id, subject=plan.subject, check=check, run_id=run_id, verdict=verdict
    )


def verification_authority(owner: Identity, verifier="ci") -> VerificationAuthority:
    return VerificationAuthority(verifier=verifier, owners=(owner,))
