"""Bounded static flow analysis; native execution and routing stay in Run Engine."""

from collections.abc import Iterable
from functools import cached_property
from graphlib import CycleError, TopologicalSorter

from flareward.programs.domain.models import GraphDefinition, JoinPolicy
from flareward.programs.interfaces import BindingContractError

type Guard = frozenset[tuple[str, str]]
type Activation = frozenset[Guard] | None


class GraphFlow:
    MAX_TERMS = 256
    MAX_REACH_CACHE = 64

    def __init__(self, graph: GraphDefinition) -> None:
        self.graph = graph
        self._routes = {
            route.source: frozenset(route.branches.values()) for route in graph.conditions
        }
        self._outgoing = {
            step.uid: self._routes.get(step.uid, frozenset(graph.edges.get(step.uid, ())))
            for step in graph.steps
        }
        self._reachable: dict[str, frozenset[str]] = {}

    def reaches(self, source: str, target: str) -> bool:
        if source not in self._reachable:
            pending, visited = [source], set()
            while pending:
                uid = pending.pop()
                if uid not in visited:
                    visited.add(uid)
                    pending.extend(self._outgoing[uid])
            if len(self._reachable) >= self.MAX_REACH_CACHE:
                self._reachable.pop(next(iter(self._reachable)))
            self._reachable[source] = frozenset(visited)
        return target in self._reachable[source]

    @classmethod
    def _minimal(cls, terms: Iterable[Guard]) -> Activation:
        minimal: set[Guard] = set()
        for term in terms:
            if any(existing <= term for existing in minimal):
                continue
            minimal = {existing for existing in minimal if not term < existing}
            minimal.add(term)
            if len(minimal) > cls.MAX_TERMS:
                return None
        return frozenset(minimal)

    @cached_property
    def _activations(self) -> dict[str, Activation] | None:
        predecessors: dict[str, set[str]] = {uid: set() for uid in self._outgoing}
        for source, targets in self._outgoing.items():
            for target in targets:
                predecessors[target].add(source)
        try:
            order = tuple(TopologicalSorter(predecessors).static_order())
        except CycleError:
            return None
        activations: dict[str, Activation] = {self.graph.entry: frozenset({frozenset()})}
        for uid in order:
            if uid == self.graph.entry:
                continue
            parents = predecessors[uid]
            if any(activations[parent] is None for parent in parents):
                activations[uid] = None
                continue
            activations[uid] = self._minimal(
                term | ({(parent, uid)} if parent in self._routes else set())
                for parent in sorted(parents)
                for term in sorted(
                    activations[parent] or (), key=lambda value: (len(value), tuple(sorted(value)))
                )
            )
        return activations

    def require_result(self, producer: str, consumer: str) -> None:
        if producer == consumer:
            raise BindingContractError("A call cannot consume its own result before execution")
        if not self.reaches(producer, consumer):
            raise BindingContractError(
                "Result consumption requires an ordering path from its producer"
            )
        activations = self._activations
        if activations is None or self.graph.join_policy == JoinPolicy.ALL:
            return
        provided, required = activations[producer], activations[consumer]
        if (
            provided is not None
            and required is not None
            and any(not any(available <= path for available in provided) for path in required)
        ):
            raise BindingContractError("Result producer is optional on an active consumer path")

    def ordered(self, left: str, right: str) -> bool:
        return self._activations is not None and (
            self.reaches(left, right) or self.reaches(right, left)
        )
