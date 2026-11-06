"""Credential upkeep joins the existing application reconciler, not program scheduling."""

from typing import Protocol


class CredentialMaintenance(Protocol):
    async def reconcile(self, limit: int = 100) -> None: ...
