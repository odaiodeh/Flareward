"""Atomic application admission port; hosts retain scheduling and cleanup ownership."""

from typing import Protocol

from lumora.executions.domain.budgets import WorkBudget, WorkReservation, WorkUsage
from lumora.models import Model


class WorkAdmission(Model):
    budget: WorkBudget
    reservation: WorkReservation | None = None


class WorkBudgetRepository(Protocol):
    async def initialize(self, budget: WorkBudget) -> None:
        """Idempotently freeze a root's owner and allowances; reject replacement."""
        ...

    async def reserve(self, budget: WorkBudget, reservation: WorkReservation) -> WorkUsage:
        """Atomically spend once; changed work or exhausted allowances must reject."""
        ...

    async def usage(self, budget: WorkBudget) -> WorkUsage: ...
