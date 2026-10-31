"""Actual legacy JSON/BSON dates, isolated owners and cross-client pending decisions."""

import pytest
from mas.application.sharing.notifications import ShareStorageError
from mas.core.identity import Identity
from mas.domain.sharing import ShareDirection
from outbound.mongo.share_notifications import MongoShareNotifications
from support.share_notification_contracts import verify_notification_repository
from support.sharing import invitation, repository_invitations


async def test_mongo_notification_contract_handles_legacy_and_native_records(mongo_database):
    documents = [
        item.model_dump(mode="json" if index % 2 else "python", exclude={"is_expired"})
        for index, item in enumerate(repository_invitations())
    ]
    await mongo_database.shares.insert_many(documents)
    repository = MongoShareNotifications(mongo_database)
    await repository.initialize()
    await verify_notification_repository(repository)


async def test_user_regex_characters_are_literal_and_bad_documents_are_private(mongo_database):
    repository = MongoShareNotifications(mongo_database)
    for name in ("literal+user", "literalluser"):
        await mongo_database.shares.insert_one(
            invitation(name, recipient_identity=Identity.user(name)).model_dump(mode="json")
        )
    found = await repository.list(
        Identity.user("literal+user"), ShareDirection.RECEIVED, None, 0, 100
    )
    assert [item.share_id for item in found] == ["literal+user"]
    await mongo_database.shares.update_one(
        {"share_id": "literal+user"}, {"$set": {"created_at": "private-invalid-date"}}
    )
    with pytest.raises(ShareStorageError) as failure:
        await repository.get("literal+user")
    assert "private" not in str(failure.value)


async def test_unicode_regex_equivalents_cannot_cross_domain_identity_boundaries(mongo_database):
    repository = MongoShareNotifications(mongo_database)
    for name in ("useri", "userİ"):
        await mongo_database.shares.insert_one(
            invitation(name, recipient_identity=Identity.user(name)).model_dump(mode="json")
        )
    found = await repository.list(Identity.user("useri"), ShareDirection.RECEIVED, None, 0, 1)
    assert [item.share_id for item in found] == ["useri"]
