"""Indexed ownership-state queries match memory and reject divergent projections."""

import pytest
from support.check_jobs import assert_pending_job_queries, check_job_scenario

from flareward.services.verification.adapters.mongo.check_runs import MongoCheckRunRepository
from flareward.services.verification.ports import VerificationStorageError


async def test_mongo_pending_job_queries_and_state_projections(mongo_database):
    repository = MongoCheckRunRepository(mongo_database)
    await repository.initialize()
    records = await assert_pending_job_queries(check_job_scenario(repository))
    assert (await repository.get(records[0].intent_id)).job_state == "closed"
    await mongo_database.verification_check_runs.update_one(
        {"_id": records[0].intent_id}, {"$set": {"job_state": "active"}}
    )
    with pytest.raises(VerificationStorageError):
        await repository.pending_jobs(after="", limit=100)
    with pytest.raises(VerificationStorageError):
        await repository.get(records[0].intent_id)
