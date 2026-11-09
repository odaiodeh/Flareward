"""Normal node factories whose runtime behavior tests declared state-write contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict

from flareward.elements.factory import BaseFactory
from flareward.elements.node import BaseNode
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import ElementStep, GraphDefinition, PathBinding
from flareward.programs.graph.state.state_view import StateView
from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.bundles import ResourceDefinition, ResourceKey
from flareward.resources.domain.categories import ResourceCategory


class Mutation(StrEnum):
    VALID = "valid"
    UNDECLARED = "undeclared"
    INVALID_TYPE = "invalid_type"


class StateConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    mutation: Mutation = Mutation.VALID


class StateNode(BaseNode):
    WRITES = {"output", "user_prompt"}

    def __init__(self, mutation: Mutation) -> None:
        super().__init__()
        self._mutation = mutation

    async def run(self, state: StateView) -> StateView:
        state["output"] = "answer"
        if self._mutation == Mutation.UNDECLARED:
            state["user_prompt"] = "private-undeclared-change"
        elif self._mutation == Mutation.INVALID_TYPE:
            state["output"] = {"private": "invalid-channel-value"}
        return state


class StateFactory(BaseFactory[StateConfig, StateNode]):
    def accepts(self, cfg: StateConfig, element_type: str) -> bool:
        return element_type == "platform_state_node"

    def create(self, cfg: StateConfig, **deps: object) -> StateNode:
        return StateNode(cfg.mutation)


class StateSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_state_node"
    name = "State-contract node"
    description = "Exercise actual node returns through the receiving state boundary"
    config_schema = StateConfig
    factory_cls = StateFactory
    writes = {"output"}


ELEMENT_SPECIFICATIONS = (StateSpec,)


def state_graph(mutation: Mutation, profile: str = "thread") -> GraphDefinition:
    resource = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.NODE, rid="state"),
        type_key=StateSpec.type_key,
        config={"mutation": mutation.value},
    )
    return GraphDefinition(
        resources=(resource,),
        steps=(
            ElementStep(
                uid="state", element=resource.key, execution=ExecutionSelection(profile=profile)
            ),
        ),
        entry="state",
        exit="state",
        outputs={"answer": PathBinding(path=("output",))},
    )
