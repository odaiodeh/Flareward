"""The memory adapter obeys the same session query/deletion contract as external storage."""

from outbound.memory.session_store import MemorySessionStore
from support.session_store_contracts import assert_query_and_delete_contracts


async def test_memory_session_queries_and_guarded_deletion():
    await assert_query_and_delete_contracts(MemorySessionStore())
