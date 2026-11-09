"""Optional asynchronous preparation performed inside the owned construction scope."""

from typing import Protocol, runtime_checkable


@runtime_checkable
class ElementPreparation(Protocol):
    async def prepare_element(self) -> None:
        """Acquire metadata or resources before a dependent factory consumes this element."""
        ...
