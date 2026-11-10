"""
Redis-backed stream monitor — query side.

Provides read-only metadata about session streams:
  - Per-session status (event count, last ID, active flag)
  - List of all currently active sessions

Uses XINFO STREAM for per-stream metadata and a Redis Set
for efficient active-session tracking.
"""

import logging
from typing import Any, Dict, List, Optional

from redis import Redis
from redis.exceptions import RedisError

from lumora.elements.messaging.adapters.redis.constants import (
    ACTIVE_SESSIONS_KEY,
    STREAM_PREFIX,
    StreamField,
)
from lumora.elements.messaging.channels import SessionStreamMonitor

logger = logging.getLogger(__name__)


class RedisStreamMonitor(SessionStreamMonitor):
    def __init__(self, redis_client: Redis) -> None:
        self._redis = redis_client

    def is_available(self) -> bool:
        try:
            return self._redis.ping()
        except RedisError:
            return False

    def get_status(self, session_id: str) -> Optional[Dict[str, Any]]:
        stream_key = f"{STREAM_PREFIX}{session_id}"
        try:
            info = self._redis.xinfo_stream(stream_key)
        except RedisError:
            return None

        last_entry = info.get("last-entry")
        is_closed = last_entry is not None and StreamField.CONTROL.encode() in last_entry[1]

        last_id = info.get("last-generated-id")

        return {
            "session_id": session_id,
            "event_count": info["length"],
            "last_event_id": last_id.decode() if isinstance(last_id, bytes) else last_id,
            "is_active": not is_closed,
        }

    def list_active(self) -> List[str]:
        try:
            members = self._redis.smembers(ACTIVE_SESSIONS_KEY)
            return [m.decode() if isinstance(m, bytes) else m for m in members]
        except RedisError as e:
            logger.error(f"Failed to list active sessions: {e}")
            return []
