"""An application-port double keeps retired audit and discards private material."""

from datetime import datetime

from mas.application.access.issuance import (
    CredentialIssuanceClosed,
    CredentialIssuanceConflict,
    CredentialMaterial,
    CredentialReservation,
)
from pydantic import SecretStr


class MemoryCredentialMaterial:
    def __init__(self) -> None:
        self.reservations: dict[str, CredentialReservation] = {}
        self.credentials: dict[str, SecretStr] = {}
        self.retired: set[str] = set()
        self.cleanup: set[str] = set()

    async def reserve(self, candidate: CredentialMaterial) -> CredentialMaterial:
        row = candidate.reservation
        saved = self.reservations.setdefault(row.binding_id, row)
        if saved.request_sha256 != row.request_sha256:
            raise CredentialIssuanceConflict()
        if row.binding_id in self.retired:
            raise CredentialIssuanceClosed()
        secret = self.credentials.setdefault(row.binding_id, candidate.credential)
        return CredentialMaterial(saved, secret)

    async def pending(self, *, after: str, limit: int) -> list[CredentialReservation]:
        return [
            row
            for key, row in sorted(self.reservations.items())
            if key > after and key not in self.retired
        ][:limit]

    async def retire(self, binding_id: str) -> None:
        if binding_id not in self.retired:
            self.cleanup.add(binding_id)
        self.retired.add(binding_id)
        self.credentials.pop(binding_id, None)

    async def expire(self, reservation: CredentialReservation, *, now: datetime) -> bool:
        if reservation.maximum_expiry > now or reservation.binding_id in self.retired:
            return False
        await self.retire(reservation.binding_id)
        return True

    async def cleanup_pending(self, *, after: str, limit: int) -> list[CredentialReservation]:
        return [self.reservations[key] for key in sorted(self.cleanup) if key > after][:limit]

    async def cleaned(self, binding_id: str) -> None:
        self.cleanup.discard(binding_id)
