"""Durable review acceptance and notification intent commit in one Mongo CAS."""

from datetime import datetime
from typing import Any

from pydantic import ValidationError
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.write_concern import WriteConcern

from flareward.services.access.adapters.mongo.credential_lifecycle import MongoCredentialLifecycle
from flareward.services.identity.domain import Identity
from flareward.services.reviews.access import StoredReviewGrant
from flareward.services.reviews.domain.models import ReviewRecord, ReviewStatus
from flareward.services.reviews.ports import ReviewMissing, ReviewStorageError


class MongoReviewRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "program_reviews", write_concern=WriteConcern(w="majority")
        )

    async def initialize(self) -> None:
        await self._collection.create_index([("reviewers", 1), ("created", -1), ("_id", 1)])
        await self._collection.create_index([("pending", 1), ("_id", 1)])
        await self._collection.create_index([("delivery_pending", 1), ("_id", 1)])
        await self._collection.create_index(
            [
                ("owner_type", 1),
                ("owner_id", 1),
                ("root_execution_id", 1),
                ("created", -1),
                ("_id", 1),
            ]
        )

    @staticmethod
    def _document(review: ReviewRecord) -> dict[str, Any]:
        return {
            "_id": review.review_id,
            "revision": review.revision,
            "reviewers": sorted(review.reviewers),
            "owner_type": review.owner.type.value,
            "owner_id": review.owner.id,
            "root_execution_id": review.root_execution_id,
            "created": review.created_at.timestamp(),
            "pending": review.status == ReviewStatus.PENDING,
            "delivery_pending": review.delivery_pending,
            "data": review.model_dump_json(),
        }

    @staticmethod
    def _decode(document: dict[str, Any]) -> ReviewRecord:
        try:
            review = ReviewRecord.model_validate_json(document["data"])
            if (
                review.review_id != document["_id"]
                or review.revision != document["revision"]
                or sorted(review.reviewers) != document["reviewers"]
                or (review.status == ReviewStatus.PENDING) != document["pending"]
                or review.delivery_pending != document["delivery_pending"]
                or review.owner.type.value != document["owner_type"]
                or review.owner.id != document["owner_id"]
                or review.root_execution_id != document["root_execution_id"]
            ):
                raise ReviewStorageError("Review storage identity is invalid")
            return review
        except ValidationError, KeyError, TypeError:
            raise ReviewStorageError("Review storage record is invalid") from None

    async def create(self, review: ReviewRecord) -> bool:
        if review.revision != 0 or review.status != ReviewStatus.PENDING:
            raise ValueError("Review must start pending")
        try:
            await self._collection.insert_one(self._document(review))
            return True
        except DuplicateKeyError:
            return False
        except PyMongoError:
            raise ReviewStorageError("Review storage is unavailable") from None

    async def get(self, review_id: str) -> ReviewRecord | None:
        try:
            document = await self._collection.find_one({"_id": review_id})
            return self._decode(document) if document is not None else None
        except PyMongoError:
            raise ReviewStorageError("Review storage is unavailable") from None

    async def save(self, review: ReviewRecord, *, expected_revision: int) -> bool:
        if review.revision != expected_revision + 1:
            raise ValueError("Review update requires the next revision")
        document = self._document(review)
        document.pop("_id")
        try:
            result = await self._collection.update_one(
                {"_id": review.review_id, "revision": expected_revision}, {"$set": document}
            )
            return result.modified_count == 1
        except PyMongoError:
            raise ReviewStorageError("Review storage is unavailable") from None

    async def _find(self, query: dict[str, Any], limit: int) -> list[ReviewRecord]:
        try:
            return [
                self._decode(document)
                async for document in self._collection.find(query).sort("_id", 1).limit(limit)
            ]
        except PyMongoError:
            raise ReviewStorageError("Review storage is unavailable") from None

    async def inbox(self, reviewer: str, *, after: str, limit: int) -> list[ReviewRecord]:
        return await self._page({"reviewers": reviewer}, after=after, limit=limit)

    async def for_execution(
        self, root_execution_id: str, owner: Identity, *, after: str, limit: int
    ) -> list[ReviewRecord]:
        return await self._page(
            {
                "owner_type": owner.type.value,
                "owner_id": owner.id,
                "root_execution_id": root_execution_id,
            },
            after=after,
            limit=limit,
        )

    async def _page(self, query: dict[str, Any], *, after: str, limit: int) -> list[ReviewRecord]:
        try:
            if after:
                cursor = await self._collection.find_one({**query, "_id": after})
                if cursor is None:
                    raise ReviewMissing("Review cursor not found")
                query["$or"] = [
                    {"created": {"$lt": cursor["created"]}},
                    {"created": cursor["created"], "_id": {"$gt": after}},
                ]
            return [
                self._decode(document)
                async for document in self._collection.find(query)
                .sort([("created", -1), ("_id", 1)])
                .limit(limit)
            ]
        except PyMongoError:
            raise ReviewStorageError("Review storage is unavailable") from None

    async def pending(self, *, after: str, limit: int) -> list[ReviewRecord]:
        return await self._find({"pending": True, "_id": {"$gt": after}}, limit)

    async def deliveries(self, *, after: str, limit: int) -> list[ReviewRecord]:
        return await self._find({"delivery_pending": True, "_id": {"$gt": after}}, limit)


class MongoReviewAccessRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._collection = database.get_collection(
            "review_access_grants", write_concern=WriteConcern(w="majority")
        )
        self._lifecycle = MongoCredentialLifecycle(self._collection)

    async def initialize(self) -> None:
        try:
            await self._lifecycle.initialize()
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    @staticmethod
    def _document(access: StoredReviewGrant) -> dict[str, Any]:
        return {
            "_id": access.grant.grant_id,
            "revoked": False,
            "data": access.model_dump_json(),
            **MongoCredentialLifecycle.metadata(access.grant.expires_at, access.grant.renewal),
        }

    async def create(self, access: StoredReviewGrant) -> None:
        try:
            await self._collection.insert_one(self._document(access))
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    async def ensure(self, access: StoredReviewGrant) -> StoredReviewGrant:
        try:
            return self._decode(await self._lifecycle.ensure(self._document(access)))
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    async def get(
        self, grant_id: str, *, active_at: datetime | None = None
    ) -> StoredReviewGrant | None:
        try:
            query: dict[str, Any] = {"_id": grant_id}
            if active_at is not None:
                query.update(
                    {
                        "revoked": False,
                        "expires_at": {"$gt": active_at.timestamp()},
                        "$expr": {
                            "$gt": [{"$multiply": ["$expires_at", 1000]}, {"$toLong": "$$NOW"}]
                        },
                    }
                )
            document = await self._collection.find_one(query)
            stored = self._decode(document) if document is not None else None
            if (
                active_at is not None
                and stored is not None
                and document is not None
                and document["expires_at"] != stored.grant.expires_at.timestamp()
            ):
                raise ReviewStorageError("Review access expiry metadata is invalid")
            return stored
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    @staticmethod
    def _decode(document: dict[str, Any]) -> StoredReviewGrant:
        try:
            stored = StoredReviewGrant.model_validate_json(document["data"])
            if stored.grant.grant_id != document["_id"] or not isinstance(
                document["revoked"], bool
            ):
                raise ReviewStorageError("Review access record identity is invalid")
            return stored.model_copy(
                update={"grant": stored.grant.model_copy(update={"revoked": document["revoked"]})}
            )
        except ValidationError, KeyError, TypeError:
            raise ReviewStorageError("Review access record is invalid") from None

    async def revoke(self, grant_id: str) -> None:
        try:
            await self._collection.update_one({"_id": grant_id}, {"$set": {"revoked": True}})
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    async def pending(self, *, after: str, limit: int) -> list[StoredReviewGrant]:
        try:
            return [
                self._decode(document)
                for document in await self._lifecycle.pending(after=after, limit=limit)
            ]
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    async def expire(self, grant_id: str, expected_expiry: datetime, *, now: datetime) -> bool:
        try:
            return await self._lifecycle.expire(grant_id, expected_expiry, now=now)
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None

    async def renew(
        self, grant_id: str, expected_expiry: datetime, expires_at: datetime, *, now: datetime
    ) -> bool:
        try:
            document = await self._collection.find_one({"_id": grant_id})
            if document is None:
                return False
            stored = self._decode(document)
            grant = stored.grant
            if (
                document["revoked"]
                or grant.renewal is None
                or grant.expires_at != expected_expiry
                or grant.renewal.next_expiry(now, expected_expiry) != expires_at
            ):
                return False
            updated = stored.model_copy(
                update={"grant": grant.model_copy(update={"expires_at": expires_at})}
            ).model_dump_json()
            return await self._lifecycle.renew(
                document, updated, expected_expiry, expires_at, now=now, renewal=grant.renewal
            )
        except PyMongoError:
            raise ReviewStorageError("Review access storage is unavailable") from None
