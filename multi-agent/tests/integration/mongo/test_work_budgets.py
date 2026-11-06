"""Independent adapters contend on the same actual Mongo root document."""

from outbound.mongo.work_budgets import MongoWorkBudgets
from support.work_budgets import assert_work_budget_contract


async def test_mongo_work_budget_contract(mongo_database):
    await assert_work_budget_contract(
        MongoWorkBudgets(mongo_database), MongoWorkBudgets(mongo_database)
    )
