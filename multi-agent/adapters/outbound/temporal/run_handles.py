"""Resolve opaque native generations only at the Temporal integration boundary."""

from runengine.adapters.coordination.temporal.host import TemporalRunHost
from runengine.adapters.coordination.temporal.models import TemporalRunIdentity
from runengine.coordination.ports import RunHandle


async def get_handle(host: TemporalRunHost, value: str) -> RunHandle:
    identity = TemporalRunIdentity.decode(value)
    return (
        await host.get_pinned_handle(identity)
        if identity is not None
        else await host.get_handle(value)
    )
