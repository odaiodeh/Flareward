"""Private event source approval survives reconstruction and uses the Mongo clock."""

from datetime import UTC, datetime, timedelta

import pytest
from support.event_sources import assert_event_source_store_contract, source_registration

from lumora.executions.adapters.mongo.event_sources import MongoEventSources
from lumora.executions.events import EventSourceUnavailable


async def test_mongo_event_source_contract(mongo_database):
    store = MongoEventSources(mongo_database)
    await store.initialize()
    await assert_event_source_store_contract(store)
    expired = source_registration("e" * 32, expired=True)
    await store.create(expired)
    with pytest.raises(KeyError):
        await MongoEventSources(mongo_database).get(
            expired.definition.source_id, active_at=datetime.now(UTC) - timedelta(hours=3)
        )
    with pytest.raises(KeyError):
        await store.rotate(
            expired.definition.source_id,
            expired.definition.owner,
            0,
            "1" * 64,
            now=datetime.now(UTC) - timedelta(hours=3),
        )
    rows = [row async for row in mongo_database.program_event_sources.find({})]
    assert all("lumora-event-v1." not in row["data"] for row in rows)


async def test_corrupt_source_metadata_is_unavailable_not_approval(mongo_database):
    store = MongoEventSources(mongo_database)
    source = source_registration()
    await store.create(source)
    await mongo_database.program_event_sources.update_one({}, {"$set": {"owner_type": "team"}})
    with pytest.raises(EventSourceUnavailable):
        await store.get(source.definition.source_id)
