"""Root-wide work allowances, distinct from physical capacity and provider cost."""

import hashlib
import json
from enum import StrEnum

from pydantic import Field

from flareward.models import Model
from flareward.services.identity.domain import Identity


class WorkKind(StrEnum):
    DISPATCH = "dispatch"
    CHILD = "child"


class WorkLimit(StrEnum):
    DISPATCHES = "max_dispatches"
    CHILDREN = "max_children"
    DEPTH = "max_depth"


class WorkLimits(Model):
    # Finite ceilings also bound the retained idempotency ledger's document size.
    max_dispatches: int = Field(default=10_000, strict=True, ge=0, le=10_000)
    max_children: int = Field(default=1_000, strict=True, ge=0, le=10_000)
    max_depth: int = Field(default=32, strict=True, ge=0, le=128)


class WorkBudget(Model):
    root_execution_id: str = Field(min_length=1)
    owner: Identity
    limits: WorkLimits

    @property
    def fingerprint(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class WorkReservation(Model):
    execution_id: str = Field(min_length=1)
    key: str = Field(min_length=1, max_length=256)
    kind: WorkKind
    depth: int = Field(strict=True, ge=0)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")

    @property
    def identity(self) -> str:
        data = json.dumps([self.execution_id, self.kind.value, self.key], separators=(",", ":"))
        return hashlib.sha256(data.encode()).hexdigest()

    @property
    def signature(self) -> str:
        return hashlib.sha256(self.model_dump_json().encode()).hexdigest()


class WorkBudgetConflict(Exception):
    """An existing budget/reservation cannot be reinterpreted as different work."""


class WorkLimitExceeded(Exception):
    def __init__(self, dimension: WorkLimit) -> None:
        super().__init__(f"Execution-tree work limit exceeded: {dimension}")
        self.dimension = dimension


class WorkUsage(Model):
    budget: WorkBudget
    dispatches: int = Field(default=0, ge=0)
    children: int = Field(default=0, ge=0)

    def require_capacity(self, reservation: WorkReservation) -> None:
        limits = self.budget.limits
        if reservation.depth > limits.max_depth:
            raise WorkLimitExceeded(WorkLimit.DEPTH)
        if reservation.kind == WorkKind.DISPATCH and self.dispatches >= limits.max_dispatches:
            raise WorkLimitExceeded(WorkLimit.DISPATCHES)
        if reservation.kind == WorkKind.CHILD and self.children >= limits.max_children:
            raise WorkLimitExceeded(WorkLimit.CHILDREN)
