"""Private, revocable consent for an exact recurring invocation source."""

import hashlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from functools import partial
from typing import Protocol
from uuid import uuid4

from pydantic import AwareDatetime, Field, JsonValue

from mas.application.access.admission import WorkflowAccessAdmission
from mas.application.execution.models import StartExecution
from mas.core.identity import Identity
from mas.domain.execution.access import WorkflowAccess
from mas.domain.execution.consent import WorkflowConsent
from mas.domain.models import Model


class WorkflowConsentRequest(Model):
    requirements: tuple[WorkflowAccess, ...] = Field(min_length=1, max_length=16)
    expires_at: AwareDatetime


class WorkflowConsentStore(Protocol):
    async def create(self, consent: WorkflowConsent) -> None: ...
    async def get(
        self, consent_id: str, owner: Identity, *, active_at: datetime | None = None
    ) -> WorkflowConsent: ...
    async def revoke(self, consent_id: str, owner: Identity) -> None: ...


def consent_definition_digest(definition: dict[str, JsonValue]) -> str:
    value = json.dumps(definition, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(value.encode()).hexdigest()


class WorkflowConsents:
    def __init__(
        self,
        store: WorkflowConsentStore,
        admission: WorkflowAccessAdmission,
        *,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        self._store, self._admission = store, admission
        self._now = clock or partial(datetime.now, UTC)

    async def approve(
        self,
        request: WorkflowConsentRequest,
        source_id: str,
        definition: dict[str, JsonValue],
        prepared_sha256: str,
        invocation: StartExecution,
        owner: Identity,
        approved_by: Identity,
    ) -> WorkflowConsent:
        # Purpose schemas and current owner policy are checked without issuing tokens.
        self._admission.approve(
            invocation.model_copy(update={"workflow_access": request.requirements}),
            owner,
            approved_by,
        )
        consent = WorkflowConsent(
            consent_id=uuid4().hex,
            source_id=source_id,
            owner=owner,
            approved_by=approved_by,
            approved_at=self._now(),
            expires_at=request.expires_at,
            definition_sha256=consent_definition_digest(definition),
            prepared_sha256=prepared_sha256,
            requirements=request.requirements,
        )
        await self._store.create(consent)
        return consent

    async def get(self, consent_id: str, owner: Identity) -> WorkflowConsent:
        return await self._store.get(consent_id, owner)

    async def resolve(
        self,
        consent_id: str,
        source_id: str,
        definition: dict[str, JsonValue],
        prepared_sha256: str,
        owner: Identity,
    ) -> WorkflowConsent:
        consent = await self._store.get(consent_id, owner, active_at=self._now())
        if (
            consent.source_id != source_id
            or consent.definition_sha256 != consent_definition_digest(definition)
            or consent.prepared_sha256 != prepared_sha256
            or consent.revoked
            or consent.expires_at <= self._now()
        ):
            raise PermissionError("Workflow consent does not authorize this invocation source")
        return consent

    async def revoke(self, consent_id: str, owner: Identity) -> None:
        await self._store.revoke(consent_id, owner)
