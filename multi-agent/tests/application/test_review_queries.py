"""Portable review query contract shared with the durable adapter."""

from support.review_queries import exercise_execution_review_query
from support.reviews import MemoryReviews


async def test_execution_review_query_contract():
    await exercise_execution_review_query(MemoryReviews())
