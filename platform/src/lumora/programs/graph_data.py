"""Resolve graph input/results without transplanting schema documents or scheduling work."""

from collections.abc import Mapping
from dataclasses import dataclass, replace
from typing import Self

from lumora.programs.domain.models import GraphDefinition
from lumora.programs.graph_flow import GraphFlow
from lumora.programs.interfaces import BindingContractError, InterfaceContract, IssuePath


@dataclass(frozen=True)
class GraphDataScope:
    flow: GraphFlow
    input: InterfaceContract
    results: Mapping[str, tuple[InterfaceContract, ...]]
    state: InterfaceContract
    consumer: str | None = None

    def at(self, consumer: str) -> Self:
        return replace(self, consumer=consumer)

    def select(self, path: IssuePath) -> InterfaceContract:
        if not path or path == (GraphDefinition.RESULTS_CHANNEL,):
            return InterfaceContract.root({"type": "object"})
        if path[0] == GraphDefinition.INPUT_CHANNEL:
            return self.input.select(path[1:])
        if len(path) < 2 or path[0] != GraphDefinition.RESULTS_CHANNEL:
            return self.state.select(path)
        producer = path[1]
        if not isinstance(producer, str) or producer not in self.results:
            raise BindingContractError(
                "Result scope requires a declared operation or Program producer"
            )
        if not self.flow.reaches(self.flow.graph.entry, producer):
            raise BindingContractError("Result producer cannot be reached from the graph entry")
        if self.consumer is not None:
            self.flow.require_result(producer, self.consumer)
        selected = InterfaceContract.root({})
        for contract in self.results[producer]:
            selected = contract.select(path[2:])
        return selected
