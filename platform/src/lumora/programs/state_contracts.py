"""Admit declared graph channel access and explicit writer/reducer policies."""

from collections.abc import Mapping, Set

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.domain.models import ElementStep, GraphDefinition, GraphWritePolicy
from lumora.programs.graph_elements import GraphElementSpec
from lumora.programs.graph_flow import GraphFlow
from lumora.programs.graph_state import graph_state_type
from lumora.programs.interfaces import BindingContractError, IssuePath
from lumora.programs.state import ProgramState
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey


class StateContracts:
    def __init__(self, elements: ElementRegistry) -> None:
        self._elements = elements

    def _spec(
        self, key: ResourceKey, resources: Mapping[ResourceKey, ResourceDefinition], path: IssuePath
    ) -> type[GraphElementSpec]:
        try:
            return GraphElementSpec.require(
                self._elements.get_spec(key.category, resources[key].type_key)
            )
        except ValueError:
            raise BindingContractError("Graph work requires a graph specification", path) from None

    @staticmethod
    def _access(
        state: type[ProgramState], reads: Set[str], writes: Set[str], path: IssuePath
    ) -> None:
        channels = state.model_fields.keys()
        if (reads | writes) - channels:
            raise BindingContractError("Graph specification refers to unknown state channels", path)
        if writes & GraphDefinition.READ_ONLY_CHANNELS:
            raise BindingContractError("Graph input and result scopes are read-only", path)

    def validate(self, graph: GraphDefinition, flow: GraphFlow) -> None:
        resources = {resource.key: resource for resource in graph.resources}
        writers: dict[str, list[str]] = {}
        state = graph_state_type(graph)
        reducers = state.get_merge_strategies().keys()
        for index, step in enumerate(graph.steps):
            path: IssuePath = ("implementation", "steps", index)
            if isinstance(step, ElementStep):
                spec = self._spec(step.element, resources, path)
                self._access(state, spec.reads, spec.writes, path)
                writes = spec.writes
            else:
                writes = set(step.outputs)
                self._access(state, set(), writes, (*path, "outputs"))
            for channel in sorted(writes):
                if graph.write_policy == GraphWritePolicy.REDUCE:
                    if channel not in reducers:
                        raise BindingContractError("State channel has no declared reducer", path)
                elif any(
                    not flow.ordered(previous, step.uid) for previous in writers.get(channel, ())
                ):
                    raise BindingContractError(
                        "State channel writers require ordering or an explicit reducer policy", path
                    )
                writers.setdefault(channel, []).append(step.uid)
        for index, route in enumerate(graph.conditions):
            path = ("implementation", "conditions", index)
            spec = self._spec(route.condition, resources, path)
            self._access(state, spec.reads, spec.writes, path)
            if spec.writes:
                raise BindingContractError(
                    "Conditions return routing outcomes and cannot write graph state", path
                )
