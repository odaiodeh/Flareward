"""
Redis Streams session channel — read side.

Uses XREAD with blocking to consume events from a Redis Stream.
Always reads from ID "0" so that late-joining clients receive
the full event history (replay), then blocks for new events.

Only yields actual user data — never injects synthetic fields.
Yields None on timeout so that callers can send keepalives
without polluting the data stream.
"""

import json
from typing import Iterator, Optional

from redis import Redis

from flareward.elements.messaging.adapters.redis.constants import STREAM_PREFIX, StreamField
from flareward.elements.messaging.channels import SessionChannelReader


class RedisSessionChannelReader(SessionChannelReader):
    def __init__(
        self,
        session_id: str,
        redis_client: Redis,
        block_ms: int = 5000,
        batch_size: int = 50,
    ) -> None:
        self._session_id = session_id
        self._redis = redis_client
        self._stream_key = f"{STREAM_PREFIX}{session_id}"
        self._block_ms = block_ms
        self._batch_size = batch_size
        self._closed = False

    @property
    def session_id(self) -> str:
        return self._session_id

    def __iter__(self) -> Iterator[Optional[dict]]:
        last_id = "0"

        while not self._closed:
            results = self._redis.xread(
                {self._stream_key: last_id},
                block=self._block_ms,
                count=self._batch_size,
            )

            if not results:
                yield None
                continue

            for _, entries in results:
                for msg_id, fields in entries:
                    last_id = msg_id
                    if StreamField.CONTROL.encode() in fields:
                        return
                    yield json.loads(fields[StreamField.PAYLOAD.encode()])

    def close(self) -> None:
        self._closed = True
