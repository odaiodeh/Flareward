"""Single-document atomic reservations shared by all descendants and API/worker processes."""

from typing import Any

from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError

from flareward.executions.domain.budgets import (
    WorkBudget,
    WorkBudgetConflict,
    WorkKind,
    WorkReservation,
    WorkUsage,
)


class MongoWorkBudgets:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.execution_work_budgets

    async def initialize(self, budget: WorkBudget) -> None:
        try:
            await self._collection.insert_one(
                {
                    "_id": budget.root_execution_id,
                    "fingerprint": budget.fingerprint,
                    "budget": budget.model_dump(mode="json"),
                    "dispatches": 0,
                    "children": 0,
                    "reservations": {},
                }
            )
        except DuplicateKeyError:
            await self.usage(budget)

    @staticmethod
    def _usage(document: dict[str, Any]) -> WorkUsage:
        return WorkUsage(
            budget=WorkBudget.model_validate(document["budget"]),
            dispatches=document["dispatches"],
            children=document["children"],
        )

    async def usage(self, budget: WorkBudget) -> WorkUsage:
        document = await self._collection.find_one(
            {"_id": budget.root_execution_id, "fingerprint": budget.fingerprint},
            {"reservations": 0},
        )
        if document is None:
            raise WorkBudgetConflict("Execution-tree budget is unavailable or conflicts")
        return self._usage(document)

    async def reserve(self, budget: WorkBudget, reservation: WorkReservation) -> WorkUsage:
        counter = "dispatches" if reservation.kind == WorkKind.DISPATCH else "children"
        limit = getattr(budget.limits, "max_" + counter)
        identity = {"_id": budget.root_execution_id, "fingerprint": budget.fingerprint}
        entry = "reservations." + reservation.identity
        # A rejected/uncertain downstream dispatch keeps its allowance: never refund
        # effects that might already have happened. Repeating this exact claim is free.
        document = await self._collection.find_one_and_update(
            {
                **identity,
                entry: {"$exists": False},
                counter: {"$lt": limit},
                "$expr": {"$lte": [reservation.depth, budget.limits.max_depth]},
            },
            {"$inc": {counter: 1}, "$set": {entry: reservation.signature}},
            projection={"reservations": 0},
            return_document=ReturnDocument.AFTER,
        )
        if document is not None:
            return self._usage(document)
        document = await self._collection.find_one(
            identity, {entry: 1, "budget": 1, "dispatches": 1, "children": 1}
        )
        if document is None:
            raise WorkBudgetConflict("Execution-tree budget is unavailable or conflicts")
        previous = document.get("reservations", {}).get(reservation.identity)
        if previous is not None:
            if previous != reservation.signature:
                raise WorkBudgetConflict("Work reservation identifies different work")
            return self._usage(document)
        self._usage(document).require_capacity(reservation)
        raise WorkBudgetConflict("Work reservation could not be admitted")
