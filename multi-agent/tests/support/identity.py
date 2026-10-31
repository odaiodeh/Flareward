"""Signed identity-cookie data shared by transport and deployed-path tests."""

import hashlib
import json
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from itsdangerous import URLSafeTimedSerializer
from mas.core.async_work import await_owned
from redis.asyncio import Redis


def session_cookie(session_id: str, secret: str = "test-secret") -> str:
    return URLSafeTimedSerializer(
        secret,
        salt="cookie-session",
        serializer=json,
        signer_kwargs={"key_derivation": "hmac", "digest_method": hashlib.sha1},
    ).dumps({"_permanent": True, "session_id": session_id})


@asynccontextmanager
async def authenticated_cookie(
    redis: Redis, username: str, secret: str, *, ttl: int = 600
) -> AsyncIterator[str]:
    """Borrow the test-owned Redis client and own one actual signed-cookie identity."""
    session_id = uuid4().hex
    key = "identity:session:" + session_id
    try:
        await redis.hset(
            key,
            mapping={
                "username": username,
                "access_token": "fixture-token",
                "session_expires_at": time.time() + ttl,
            },
        )
        await redis.expire(key, ttl)
        yield session_cookie(session_id, secret)
    finally:
        await await_owned(redis.delete(key))
