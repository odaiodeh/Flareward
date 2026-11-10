"""The session-reader adapter supplies the same text contract for either Redis codec."""

from uuid import uuid4

import pytest

from lumora.services.auth.adapters.redis_sessions import RedisSessionReader
from lumora.services.connections.adapters.redis import owned_redis


@pytest.mark.parametrize("decode", [True, False])
async def test_session_reader_decodes_the_owned_transport_without_owning_its_client(
    redis_uri, decode
):
    key = "verification-session-reader:" + uuid4().hex
    async with owned_redis(redis_uri, decode_responses=decode) as redis:
        try:
            await redis.hset(
                key, mapping={"username": "developer", "access_token": "fixture-token"}
            )
            reader = RedisSessionReader(redis)
            assert await reader.hgetall(key) == {
                "username": "developer",
                "access_token": "fixture-token",
            }
            assert await redis.ping()
        finally:
            await redis.delete(key)
