"""
Composable stream operators for session channels.

Each operator takes an iterable of events (a SessionChannelReader or
any iterator that may yield None on idle) and returns a transformed
iterator.  Operators compose naturally via nesting:

    stream = with_heartbeats(reader)
    stream = with_heartbeats(filter_events(reader, types={"complete"}))
"""

from typing import Iterable, Iterator, Optional

HEARTBEAT_EVENT = {"type": "heartbeat"}


def with_heartbeats(source: Iterable[Optional[dict]]) -> Iterator[dict]:
    """Convert idle timeouts (None) into heartbeat events."""
    for event in source:
        yield event if event is not None else HEARTBEAT_EVENT
