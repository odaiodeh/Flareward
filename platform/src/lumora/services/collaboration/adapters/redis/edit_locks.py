"""Atomic asynchronous editing leases; no transport or membership policy lives here."""

from contextlib import asynccontextmanager
from urllib.parse import quote

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import RedisError

from lumora.services.collaboration.editing import EditLease, EditLockScope, EditLockUnavailable

_READ = """
local raw = redis.call('GET', KEYS[1])
local value = nil
local lease = ''
if raw then
    local ok, decoded = pcall(cjson.decode, raw)
    if not ok or type(decoded) ~= 'table'
        or type(decoded.user_id) ~= 'string' or decoded.user_id == ''
        or type(decoded.display_name) ~= 'string' then
        return redis.error_reply('Invalid edit-lock state')
    end
    value = decoded
    lease = value.lease_id
    if lease == nil or lease == cjson.null then lease = '' end
end
"""
_ACQUIRE = (
    _READ
    + """
if raw and (value.user_id ~= ARGV[3] or lease ~= ARGV[4]) then return raw end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return nil
"""
)
_RENEW = (
    _READ
    + """
if not raw then return 0 end
if value.user_id ~= ARGV[1] or lease ~= ARGV[2] then return 0 end
return redis.call('EXPIRE', KEYS[1], ARGV[3])
"""
)
_RELEASE = (
    _READ
    + """
if not raw then return 0 end
if value.user_id ~= ARGV[1] or lease ~= ARGV[2] then return 0 end
return redis.call('DEL', KEYS[1])
"""
)


def edit_lock_key(scope: EditLockScope) -> str:
    team, entity = quote(scope.team_id, safe=""), quote(scope.entity_id, safe="")
    return f"mas:collab:editlock:team:{team}:{scope.kind.value}:{entity}"


@asynccontextmanager
async def lock_errors():
    try:
        yield
    except RedisError, ValidationError:
        raise EditLockUnavailable("Editing coordination is unavailable") from None


class RedisEditLockStore:
    def __init__(self, redis: Redis) -> None:
        self._redis = redis

    async def acquire(self, scope: EditLockScope, lease: EditLease, ttl: int) -> EditLease | None:
        async with lock_errors():
            result = await self._redis.eval(
                _ACQUIRE,
                1,
                edit_lock_key(scope),
                lease.model_dump_json(exclude_none=True),
                ttl,
                lease.user_id,
                lease.lease_id or "",
            )
            return EditLease.model_validate_json(result) if result is not None else None

    async def renew(self, scope: EditLockScope, lease: EditLease, ttl: int) -> bool:
        async with lock_errors():
            return bool(
                await self._redis.eval(
                    _RENEW,
                    1,
                    edit_lock_key(scope),
                    lease.user_id,
                    lease.lease_id or "",
                    ttl,
                )
            )

    async def release(self, scope: EditLockScope, lease: EditLease) -> None:
        async with lock_errors():
            await self._redis.eval(
                _RELEASE,
                1,
                edit_lock_key(scope),
                lease.user_id,
                lease.lease_id or "",
            )

    async def holders(self, scopes: tuple[EditLockScope, ...]) -> tuple[EditLease | None, ...]:
        if not scopes:
            return ()
        async with lock_errors():
            values = await self._redis.mget([edit_lock_key(scope) for scope in scopes])
            return tuple(
                EditLease.model_validate_json(value) if value is not None else None
                for value in values
            )
