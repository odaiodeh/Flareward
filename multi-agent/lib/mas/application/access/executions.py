"""Workflow credential authority follows accepted root execution lifetime."""

from typing import Protocol

from mas.core.identity import Identity


class ExecutionAccessUnavailable(Exception):
    def __init__(self) -> None:
        super().__init__("Workflow execution authority is unavailable")


class ExecutionGrantAuthority(Protocol):
    async def active(self, root_execution_id: str, owner: Identity) -> bool: ...

    async def closed(self, root_execution_id: str, owner: Identity) -> bool:
        """Allow pre-provisioning, but refuse an existing closed or foreign root."""
        ...
