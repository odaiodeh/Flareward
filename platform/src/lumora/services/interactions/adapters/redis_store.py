"""Native async Redis interaction transport; decisions remain replayable until retention expires."""

import json
import re
from datetime import UTC, datetime

from pydantic import JsonValue
from redis.asyncio import Redis

from lumora.services.interactions.adapters.errors import redis_async
from lumora.services.interactions.adapters.wire import (
    CANCEL,
    POLL,
    RESPOND,
    SAVE_RULES,
    canonical,
    request_key,
    response_result,
    root_key,
)
from lumora.services.interactions.models import (
    RESPONSE,
    ApprovalStatus,
    ApprovalTicket,
    StreamCursorExpired,
    StreamEvent,
)
from lumora.services.interactions.tools.models import ApprovalOverrides, ApprovalResponse


def validate_cursor(cursor: str) -> None:
    if re.fullmatch(r"[0-9]{1,20}-[0-9]{1,20}", cursor) is None:
        raise ValueError("Stream cursor must be a Redis stream ID")


class RedisInteractionStore:
    def __init__(self, client: Redis, *, ttl: int = 86400, max_events: int = 10000) -> None:
        self._client = client
        self._ttl = ttl
        self._max_events = max_events

    @redis_async
    async def publish(self, root_id: str, execution_id: str, data: dict[str, JsonValue]) -> None:
        key = root_key(root_id) + ":events"
        async with self._client.pipeline(transaction=True) as transaction:
            transaction.xadd(
                key,
                {"payload": canonical({"execution_id": execution_id, "data": data})},
                maxlen=self._max_events,
            )
            transaction.expire(key, self._ttl)
            await transaction.execute()

    @redis_async
    async def read(self, root_id: str, after: str, *, block_ms: int = 500) -> list[StreamEvent]:
        validate_cursor(after)
        key = root_key(root_id) + ":events"
        await self._validate_window(key, after)
        streams = await self._client.xread(
            {key: after},
            count=100,
            block=block_ms if block_ms > 0 else None,
        )
        await self._validate_window(key, after)
        return [
            StreamEvent(cursor=cursor, **json.loads(fields["payload"]))
            for _, entries in streams
            for cursor, fields in entries
        ]

    async def _validate_window(self, key: str, after: str) -> None:
        if after == "0-0":
            return
        first = await self._client.xrange(key, count=1)
        if not first or tuple(map(int, first[0][0].split("-"))) > tuple(map(int, after.split("-"))):
            raise StreamCursorExpired(
                "Stream cursor is outside retained history; reload execution state"
            )

    @redis_async
    async def pending(self, root_id: str) -> list[ApprovalTicket]:
        base = root_key(root_id)
        result = []
        for key in sorted(await self._client.smembers(base + ":pending")):
            status, _ = await self._client.eval(
                POLL, 3, key, base + ":pending", base + ":cancelled"
            )
            if status == "missing":
                await self._client.srem(base + ":pending", key)
            if status != ApprovalStatus.PENDING.value:
                continue
            record = await self._client.hgetall(key)
            if not record:
                await self._client.srem(base + ":pending", key)
                continue
            if record.get("status") != ApprovalStatus.PENDING.value:
                continue
            result.append(
                ApprovalTicket(
                    **json.loads(record["ticket"]),
                    expires_at=datetime.fromtimestamp(float(record["expires_ms"]) / 1000, UTC),
                )
            )
        return result

    @redis_async
    async def respond(
        self, root_id: str, response: ApprovalResponse, *, allow_pending: bool = True
    ) -> None:
        base = root_key(root_id)
        code = await self._client.eval(
            RESPOND,
            4,
            request_key(root_id, response.request_id),
            base + ":pending",
            base + ":cancelled",
            base + ":events",
            canonical(RESPONSE.dump_python(response, mode="json")),
            "1" if allow_pending else "0",
            self._ttl,
            self._max_events,
        )
        response_result(code)

    @redis_async
    async def load_rules(self, root_id: str) -> ApprovalOverrides | None:
        raw = await self._client.get(root_key(root_id) + ":rules")
        return ApprovalOverrides.from_dict(json.loads(raw)) if raw else None

    @redis_async
    async def save_rules(
        self, root_id: str, rules: ApprovalOverrides, *, revision: int | None = None
    ) -> None:
        if revision is not None and revision < 0:
            raise ValueError("Approval rule revision must be nonnegative")
        await self._client.eval(
            SAVE_RULES,
            1,
            root_key(root_id) + ":rules",
            canonical(rules.to_dict()),
            self._ttl,
            "" if revision is None else str(revision),
        )

    @redis_async
    async def cancel(self, execution_id: str, *, root_execution_id: str | None = None) -> None:
        root_id = root_execution_id or execution_id
        await self._client.eval(
            CANCEL,
            1,
            root_key(root_id) + ":cancelled",
            "*" if execution_id == root_id else execution_id,
            self._ttl,
        )
