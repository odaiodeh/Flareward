"""Recoverable human issuance; private material is separate from portable run data."""

import hashlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from functools import partial
from typing import Protocol

from pydantic import AwareDatetime, BaseModel, Field, SecretStr, ValidationError

from mas.application.access.credentials import OpaqueCredentials, WorkflowCredentialUnavailable
from mas.application.access.executions import ExecutionAccessUnavailable, ExecutionGrantAuthority
from mas.core.identity import Identity
from mas.domain.credential_grants import WorkflowGrant
from mas.domain.credential_leases import CredentialLease
from mas.domain.models import Model


class CredentialIssuanceConflict(ValueError):
    def __init__(self) -> None:
        super().__init__("Credential issuance key belongs to a different request")


class CredentialIssuanceClosed(PermissionError):
    def __init__(self) -> None:
        super().__init__("Credential issuance is retired or expired")


class CredentialMaterialUnavailable(WorkflowCredentialUnavailable):
    def __init__(self) -> None:
        super().__init__("Private credential material is unavailable")


class CredentialReservation(Model):
    binding_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    request_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    purpose: str
    owner: Identity
    issued_by: Identity
    root_execution_id: str = Field(min_length=1)
    grant_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    grant_json: str = Field(repr=False)
    maximum_expiry: AwareDatetime
    delivery_key: str | None = None


@dataclass(frozen=True)
class CredentialMaterial:
    reservation: CredentialReservation
    credential: SecretStr = field(repr=False)


class CredentialMaterialStore(Protocol):
    async def reserve(self, candidate: CredentialMaterial) -> CredentialMaterial: ...
    async def pending(self, *, after: str, limit: int) -> Sequence[CredentialReservation]: ...
    async def retire(self, binding_id: str) -> None: ...
    async def expire(self, reservation: CredentialReservation, *, now: datetime) -> bool: ...
    async def cleanup_pending(
        self, *, after: str, limit: int
    ) -> Sequence[CredentialReservation]: ...
    async def cleaned(self, binding_id: str) -> None: ...


class CredentialDelivery(Protocol):
    @property
    def key(self) -> str: ...
    async def deliver(self, material: CredentialMaterial) -> None: ...
    async def retire(self, reservation: CredentialReservation) -> None: ...


@dataclass(frozen=True)
class CredentialStatus:
    root_execution_id: str
    revoked: bool


class ManagedCredentialOwner(Protocol):
    async def credential_status(
        self, grant_id: str, owner: Identity
    ) -> CredentialStatus | None: ...
    async def revoke(self, grant_id: str, owner: Identity) -> None: ...


def digest(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    ).hexdigest()


def confirmed_grant[Grant: WorkflowGrant](
    expected: Grant,
    persisted: Grant,
    credential: SecretStr,
    secret_sha256: str,
    codec: OpaqueCredentials,
    now: datetime,
) -> Grant:
    """Recovery may observe renewal/revocation, never different original authority."""
    if (
        codec.identify(credential.get_secret_value()) != expected.grant_id
        or not codec.matches(credential.get_secret_value(), secret_sha256)
        or persisted.model_copy(update={"expires_at": expected.expires_at, "revoked": False})
        != expected
        or persisted.expires_at < expected.expires_at
        or persisted.expires_at
        > (expected.renewal.renewable_until if expected.renewal else expected.expires_at)
    ):
        raise CredentialMaterialUnavailable()
    if persisted.revoked or persisted.expires_at <= now:
        raise CredentialIssuanceClosed()
    return persisted


class CredentialIssuance:
    def __init__(
        self,
        purpose: str,
        store: CredentialMaterialStore,
        delivery: CredentialDelivery | None = None,
    ) -> None:
        self.purpose, self._store, self._delivery = purpose, store, delivery

    async def reserve[Grant: WorkflowGrant](
        self,
        key: str,
        grant: Grant,
        credential: SecretStr,
        *,
        root: str,
        request: BaseModel,
        ttl_seconds: int,
        renewable_for_seconds: int | None,
    ) -> tuple[Grant, SecretStr]:
        if not 1 <= len(key) <= 128:
            raise ValueError("Credential issuance key must contain 1 to 128 characters")
        binding = digest([self.purpose, grant.owner.model_dump(mode="json"), key])
        intent = [grant.issued_by.model_dump(mode="json"), root, request.model_dump(mode="json")]
        delivery_key = self._delivery.key if self._delivery is not None else None
        if delivery_key is not None:
            intent.append({"delivery": delivery_key})
        request_digest = digest(intent)
        candidate = CredentialMaterial(
            CredentialReservation(
                binding_id=binding,
                request_sha256=request_digest,
                purpose=self.purpose,
                owner=grant.owner,
                issued_by=grant.issued_by,
                root_execution_id=root,
                grant_id=grant.grant_id,
                grant_json=grant.model_dump_json(),
                maximum_expiry=grant.renewal.renewable_until if grant.renewal else grant.expires_at,
                delivery_key=delivery_key,
            ),
            credential,
        )
        material = await self._store.reserve(candidate)
        saved = material.reservation
        if (
            saved.binding_id != binding
            or saved.request_sha256 != request_digest
            or saved.purpose != self.purpose
            or not saved.owner.owns(grant.owner)
            or not saved.issued_by.owns(grant.issued_by)
            or saved.root_execution_id != root
            or saved.delivery_key != delivery_key
        ):
            raise CredentialIssuanceConflict()
        try:
            restored = type(grant).model_validate_json(saved.grant_json)
        except ValidationError:
            raise CredentialMaterialUnavailable() from None
        expected = grant.model_copy(
            update={
                "grant_id": saved.grant_id,
                "issued_at": restored.issued_at,
                "expires_at": restored.issued_at + timedelta(seconds=ttl_seconds),
                "renewal": CredentialLease(
                    ttl_seconds=ttl_seconds,
                    renewable_until=restored.issued_at + timedelta(seconds=renewable_for_seconds),
                )
                if renewable_for_seconds is not None
                else None,
            }
        )
        maximum = restored.renewal.renewable_until if restored.renewal else restored.expires_at
        if restored != expected or saved.maximum_expiry != maximum:
            raise CredentialMaterialUnavailable()
        if self._delivery is not None:
            await self._delivery.deliver(material)
        return restored, material.credential


class CredentialMaterialRetirement:
    def __init__(
        self,
        store: CredentialMaterialStore,
        purposes: Mapping[str, ManagedCredentialOwner],
        authority: ExecutionGrantAuthority,
        *,
        clock: Callable[[], datetime] | None = None,
        deliveries: Sequence[CredentialDelivery] = (),
    ) -> None:
        self._store, self._purposes, self._authority = store, dict(purposes), authority
        self._now = clock or partial(datetime.now, UTC)
        self._cursor = ""
        self._cleanup_cursor = ""
        self._deliveries = {delivery.key: delivery for delivery in deliveries}

    async def reconcile(self, limit: int = 100) -> None:
        if not 1 <= limit <= 100:
            raise ValueError("Credential maintenance page size must be between 1 and 100")
        rows = await self._store.pending(after=self._cursor, limit=limit)
        if not rows and self._cursor:
            self._cursor = ""
            rows = await self._store.pending(after="", limit=limit)
        for reservation in rows:
            self._cursor = reservation.binding_id
            if reservation.maximum_expiry <= self._now():
                if await self._store.expire(reservation, now=self._now()):
                    continue
            purpose = self._purposes.get(reservation.purpose)
            if purpose is None:
                continue
            state = await purpose.credential_status(reservation.grant_id, reservation.owner)
            if state is not None and state.root_execution_id != reservation.root_execution_id:
                raise CredentialMaterialUnavailable()
            if state is not None and state.revoked:
                await self._store.retire(reservation.binding_id)
                continue
            try:
                if not await self._authority.closed(
                    reservation.root_execution_id, reservation.owner
                ):
                    continue
            except ExecutionAccessUnavailable:
                continue
            if state is not None:
                await purpose.revoke(reservation.grant_id, reservation.owner)
            await self._store.retire(reservation.binding_id)
        await self._cleanup(limit)

    async def _cleanup(self, limit: int) -> None:
        rows = await self._store.cleanup_pending(after=self._cleanup_cursor, limit=limit)
        if not rows and self._cleanup_cursor:
            self._cleanup_cursor = ""
            rows = await self._store.cleanup_pending(after="", limit=limit)
        for reservation in rows:
            self._cleanup_cursor = reservation.binding_id
            if reservation.delivery_key is not None:
                delivery = self._deliveries.get(reservation.delivery_key)
                if delivery is None:
                    continue
                await delivery.retire(reservation)
            await self._store.cleaned(reservation.binding_id)
