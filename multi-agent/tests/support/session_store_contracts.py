"""Shared persistence contracts depend only on the application-owned session port."""

from datetime import UTC, datetime, timedelta

from mas.core.identity import Identity
from mas.domain.execution.context import ExecutionContext
from mas.session.domain.dto import SessionListFilter
from mas.session.domain.session_record import SessionRecord
from mas.session.execution.session_store import SessionStore


async def assert_query_and_delete_contracts(store: SessionStore) -> None:
    owner, other = Identity.user("owner"), Identity.team("owner")
    now = datetime(2026, 1, 1, tzinfo=UTC)
    first = SessionRecord(
        run_id="first",
        identity=owner,
        blueprint_id="one",
        run_context=ExecutionContext(identity=owner, started_at=now),
    )
    second = SessionRecord(
        run_id="second",
        identity=owner,
        blueprint_id="two",
        run_context=ExecutionContext(identity=owner, started_at=now + timedelta(seconds=1)),
    )
    foreign = SessionRecord(
        run_id="foreign",
        identity=other,
        run_context=ExecutionContext(identity=other, started_at=now),
    )
    for record in (first, second, foreign):
        assert await store.create(record)
    page = await store.query(owner, SessionListFilter(), offset=0, limit=1)
    assert page.total == 2 and [record.run_id for record in page.records] == ["second"]
    page = await store.query(owner, SessionListFilter(), offset=1, limit=1)
    assert page.total == 2 and [record.run_id for record in page.records] == ["first"]
    filtered = await store.query(owner, SessionListFilter(blueprint_id="two"), offset=0, limit=100)
    assert filtered.total == 1 and filtered.records == [second]
    assert (await store.query(other, SessionListFilter(), offset=0, limit=100)).records == [foreign]
    updated = first.model_copy(update={"version": 1})
    assert await store.replace(updated, expected_version=0)
    assert not await store.delete(first)
    assert not await store.delete(updated.model_copy(update={"identity": other}))
    assert await store.delete(updated)
    assert not await store.delete(updated)
    assert (await store.query(owner, SessionListFilter(), offset=0, limit=100)).records == [second]
