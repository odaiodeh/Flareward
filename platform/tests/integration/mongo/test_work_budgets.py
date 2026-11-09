"""Independent adapters contend on the same actual Mongo root document."""

from support.work_budgets import assert_work_budget_contract

from flareward.executions.adapters.mongo.work_budgets import MongoWorkBudgets


async def test_mongo_work_budget_contract(mongo_database):
    await assert_work_budget_contract(
        MongoWorkBudgets(mongo_database), MongoWorkBudgets(mongo_database)
    )
