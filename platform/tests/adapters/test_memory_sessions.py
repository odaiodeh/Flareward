"""The memory adapter obeys the same session query/deletion contract as external storage."""

from support.session_store_contracts import assert_query_and_delete_contracts

from lumora.services.sessions.adapters.memory.session_store import MemorySessionStore


async def test_memory_session_queries_and_guarded_deletion():
    await assert_query_and_delete_contracts(MemorySessionStore())
