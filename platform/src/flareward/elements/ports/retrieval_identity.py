from typing import Protocol, runtime_checkable


@runtime_checkable
class RetrievalIdentity(Protocol):
    """Identity contract for access-controlled retrieval."""

    @property
    def identity_id(self) -> str: ...
