"""Real durable review queries preserve owner/root/cursor and projection integrity."""

import pytest
from mas.application.reviews.ports import ReviewStorageError
from outbound.mongo.reviews import MongoReviewRepository
from support.review_queries import exercise_execution_review_query


async def test_execution_review_query_contract(mongo_database):
    repository = MongoReviewRepository(mongo_database)
    await repository.initialize()
    await exercise_execution_review_query(repository)


@pytest.mark.parametrize("field", ["owner_type", "owner_id", "root_execution_id"])
async def test_review_query_projection_cannot_disagree_with_the_record(mongo_database, field):
    repository = MongoReviewRepository(mongo_database)
    await exercise_execution_review_query(repository)
    identifier = f"{1:064x}"
    await mongo_database.program_reviews.update_one({"_id": identifier}, {"$set": {field: "wrong"}})
    with pytest.raises(ReviewStorageError):
        await repository.get(identifier)
