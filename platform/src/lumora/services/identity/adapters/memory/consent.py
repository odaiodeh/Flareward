"""Composition-owned ephemeral consent for explicitly in-memory deployments."""


class MemoryConsents:
    def __init__(self) -> None:
        self._accepted: set[tuple[str, str]] = set()

    async def accepted(self, user: str, version: str) -> bool:
        return (user, version) in self._accepted

    async def accept(self, user: str, version: str) -> None:
        self._accepted.add((user, version))
