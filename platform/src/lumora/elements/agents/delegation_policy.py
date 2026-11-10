"""Delegation policy filters supplied candidates without graph-state dependencies."""

from abc import ABC, abstractmethod
from collections.abc import Iterable, Mapping


class DelegationPolicy(ABC):
    def __init__(self, candidates: Iterable[str]) -> None:
        self._candidates = frozenset(candidates)

    @abstractmethod
    def is_delegable(self, node_uid: str) -> bool: ...

    def filter_delegable_nodes[T](self, candidates: Mapping[str, T]) -> dict[str, T]:
        return {uid: candidate for uid, candidate in candidates.items() if self.is_delegable(uid)}


class PermissiveDelegationPolicy(DelegationPolicy):
    def is_delegable(self, node_uid: str) -> bool:
        return node_uid in self._candidates
