"""Explicit authority double for tests concerned with grant scope rather than execution."""

from dataclasses import dataclass

from lumora.services.identity.domain import Identity


@dataclass
class ExecutionAuthority:
    live: bool = True
    ended: bool = False

    async def active(self, root_execution_id: str, owner: Identity) -> bool:
        return self.live

    async def closed(self, root_execution_id: str, owner: Identity) -> bool:
        return self.ended
