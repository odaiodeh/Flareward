"""Shared Redis wire contract for async APIs and synchronous legacy invocation workers."""

import hashlib
import json

from pydantic import JsonValue

from lumora.services.interactions.models import REQUEST, InteractionConflict
from lumora.services.interactions.tools.models import ApprovalRequest

PREFIX = "lumora:interaction:"


def root_key(root_id: str) -> str:
    return PREFIX + "{" + hashlib.sha256(root_id.encode()).hexdigest() + "}"


def request_key(root_id: str, request_id: str) -> str:
    return root_key(root_id) + ":approval:" + hashlib.sha256(request_id.encode()).hexdigest()


def canonical(value: JsonValue) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def approval_event(request: ApprovalRequest) -> dict[str, JsonValue]:
    data = REQUEST.dump_python(request, mode="json")
    return {
        **data,
        "type": "approval_required",
        "approval_type": data["type"],
        "node": request.origin.node_uid,
        "display_name": request.origin.node_display_name,
    }


def response_result(code: int) -> None:
    if code == 0:
        raise KeyError("Approval request does not exist")
    if code < 0:
        raise InteractionConflict(
            "Approval has expired, was cancelled, or already has another decision"
        )


# All keys share the root hash tag so transactions also work on Redis Cluster.
_CANCELLED = """
local function is_cancelled(key, scope)
    local kind = redis.call('TYPE', key).ok
    if kind == 'string' then return true end
    if kind == 'none' then return false end
    if redis.call('SISMEMBER', key, '*') == 1 then return true end
    for _, execution_id in ipairs(scope) do
        if redis.call('SISMEMBER', key, execution_id) == 1 then return true end
    end
    return false
end
"""

CHECK_CANCELLED = _CANCELLED + "return is_cancelled(KEYS[1], cjson.decode(ARGV[1]))"

CLOSE_PENDING = """
if redis.call('HGET', KEYS[1], 'ticket') == ARGV[1]
    and redis.call('HGET', KEYS[1], 'status') == 'pending' then
    redis.call('HSET', KEYS[1], 'status', 'cancelled')
    redis.call('SREM', KEYS[2], KEYS[1])
end
return 1
"""

CANCEL = """
if redis.call('TYPE', KEYS[1]).ok ~= 'string' then redis.call('SADD', KEYS[1], ARGV[1]) end
redis.call('EXPIRE', KEYS[1], ARGV[2])
return 1
"""

CREATE = (
    _CANCELLED
    + """
if redis.call('EXISTS', KEYS[1]) == 1 then
    if redis.call('HGET', KEYS[1], 'ticket') == ARGV[1] then return 2 end
    return -3
end
if is_cancelled(KEYS[4], cjson.decode(ARGV[6])) then return -2 end
local now = redis.call('TIME')
local deadline = now[1] * 1000 + math.floor(now[2] / 1000) + tonumber(ARGV[2])
redis.call('HSET', KEYS[1], 'ticket', ARGV[1], 'status', 'pending', 'expires_ms', deadline)
redis.call('HSET', KEYS[1], 'scope', ARGV[6])
redis.call('EXPIRE', KEYS[1], ARGV[3])
redis.call('SADD', KEYS[2], KEYS[1])
redis.call('EXPIRE', KEYS[2], ARGV[3])
redis.call('XADD', KEYS[3], 'MAXLEN', '~', ARGV[5], '*', 'payload', ARGV[4])
redis.call('EXPIRE', KEYS[3], ARGV[3])
return 1
"""
)

RESPOND = (
    _CANCELLED
    + """
if redis.call('EXISTS', KEYS[1]) == 0 then return 0 end
local status = redis.call('HGET', KEYS[1], 'status')
if status == 'responded' then
    if redis.call('HGET', KEYS[1], 'response') == ARGV[1] then return 2 end
    return -3
end
local scope = cjson.decode(redis.call('HGET', KEYS[1], 'scope') or '[]')
if is_cancelled(KEYS[3], scope) then return -2 end
if ARGV[2] == '0' then return -2 end
local now = redis.call('TIME')
local ms = now[1] * 1000 + math.floor(now[2] / 1000)
if status ~= 'pending' then return -1 end
if ms >= tonumber(redis.call('HGET', KEYS[1], 'expires_ms')) then
    redis.call('HSET', KEYS[1], 'status', 'expired')
    redis.call('SREM', KEYS[2], KEYS[1])
    return -1
end
redis.call('HSET', KEYS[1], 'status', 'responded', 'response', ARGV[1])
redis.call('SREM', KEYS[2], KEYS[1])
local ticket = cjson.decode(redis.call('HGET', KEYS[1], 'ticket'))
local response = cjson.decode(ARGV[1])
local event = cjson.encode({execution_id=ticket.execution_id, data={
    type='approval_resolved', request_id=response.request_id, decision=response.decision,
    feedback=response.feedback
}})
redis.call('XADD', KEYS[4], 'MAXLEN', '~', ARGV[4], '*', 'payload', event)
redis.call('EXPIRE', KEYS[4], ARGV[3])
return 1
"""
)

POLL = (
    _CANCELLED
    + """
if redis.call('EXISTS', KEYS[1]) == 0 then return {'missing', ''} end
local status = redis.call('HGET', KEYS[1], 'status')
local scope = cjson.decode(redis.call('HGET', KEYS[1], 'scope') or '[]')
if is_cancelled(KEYS[3], scope) then
    if status == 'pending' then
        redis.call('HSET', KEYS[1], 'status', 'cancelled')
        redis.call('SREM', KEYS[2], KEYS[1])
    end
    return {'cancelled', ''}
end
if status == 'responded' then return {status, redis.call('HGET', KEYS[1], 'response')} end
local now = redis.call('TIME')
local ms = now[1] * 1000 + math.floor(now[2] / 1000)
if status == 'pending' and ms >= tonumber(redis.call('HGET', KEYS[1], 'expires_ms')) then
    status = 'expired'
    redis.call('HSET', KEYS[1], 'status', status)
    redis.call('SREM', KEYS[2], KEYS[1])
end
return {status, ''}
"""
)

# Keep the session revision in the same cache value as policy. Readers ignore
# this adapter-owned field; canonical replacement preserves the revision fence.
SAVE_RULES = """
local previous = redis.call('GET', KEYS[1])
local revision = -1
if previous then
    revision = tonumber(cjson.decode(previous)._session_revision or -1)
end
if ARGV[3] ~= '' then
    local incoming = tonumber(ARGV[3])
    if incoming <= revision then
        redis.call('EXPIRE', KEYS[1], ARGV[2])
        return 0
    end
    revision = incoming
end
local policy = ARGV[1]
if revision >= 0 then
    policy = string.sub(policy, 1, -2) .. ',"_session_revision":' .. tostring(revision) .. '}'
end
redis.call('SET', KEYS[1], policy, 'EX', ARGV[2])
return 1
"""
