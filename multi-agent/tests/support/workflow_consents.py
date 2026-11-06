"""Detached consent port double and common ownership/revocation persistence assertions."""

from datetime import datetime

import pytest
from mas.application.access.consent import WorkflowConsentStore
from mas.core.identity import Identity
from mas.domain.execution.consent import WorkflowConsent


class MemoryWorkflowConsents:
    def __init__(self) -> None:
        self.records: dict[str, str] = {}

    async def create(self, consent: WorkflowConsent) -> None:
        if consent.consent_id in self.records:
            raise ValueError("Consent identity already exists")
        self.records[consent.consent_id] = consent.model_dump_json()

    async def get(
        self, consent_id: str, owner: Identity, *, active_at: datetime | None = None
    ) -> WorkflowConsent:
        value = self.records.get(consent_id)
        row = WorkflowConsent.model_validate_json(value) if value is not None else None
        if (
            row is None
            or not row.owner.owns(owner)
            or (active_at is not None and (row.revoked or row.expires_at <= active_at))
        ):
            raise PermissionError("Workflow consent is unavailable or no longer active")
        return row

    async def revoke(self, consent_id: str, owner: Identity) -> None:
        row = await self.get(consent_id, owner)
        self.records[consent_id] = row.model_copy(update={"revoked": True}).model_dump_json()


async def assert_consent_store_contract(
    store: WorkflowConsentStore, consent: WorkflowConsent
) -> None:
    await store.create(consent)
    assert (
        await store.get(consent.consent_id, consent.owner, active_at=consent.approved_at) == consent
    )
    foreign = (
        Identity.team(consent.owner.id)
        if consent.owner.is_user
        else Identity.user(consent.owner.id)
    )
    with pytest.raises(PermissionError):
        await store.get(consent.consent_id, foreign)
    with pytest.raises(PermissionError):
        await store.revoke(consent.consent_id, foreign)
    with pytest.raises(PermissionError):
        await store.get(consent.consent_id, consent.owner, active_at=consent.expires_at)
    await store.revoke(consent.consent_id, consent.owner)
    await store.revoke(consent.consent_id, consent.owner)
    assert await store.get(consent.consent_id, consent.owner) == consent.model_copy(
        update={"revoked": True}
    )
    with pytest.raises(PermissionError):
        await store.get(consent.consent_id, consent.owner, active_at=consent.approved_at)
