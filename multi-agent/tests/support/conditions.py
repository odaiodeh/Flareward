"""Installed deterministic work supplies numeric output and real outgoing IEM packets."""

from mas.application.elements.factory import BaseFactory
from mas.application.elements.node import BaseNode
from mas.application.programs.graph_elements import GraphElementSpec
from mas.core.enums import ResourceCategory
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import SystemPacket
from mas.domain.messages import ChatMessage, Role
from mas.elements.conditions.router_boolean.spec.spec import RouterBooleanConditionElementSpec
from mas.elements.conditions.router_direct.spec.spec import RouterDirectConditionElementSpec
from mas.elements.conditions.threshold.spec.spec import ThresholdConditionElementSpec
from mas.graph.state.state_view import StateView
from pydantic import BaseModel, ConfigDict


class OutputConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str
    recipients: tuple[str, ...] = ()


class OutputNode(BaseNode):
    READS = {"nodes_output", "inter_packets", "messages"}
    WRITES = {"output", "nodes_output", "inter_packets", "messages"}

    def __init__(self, value: str, recipients: tuple[str, ...]):
        super().__init__()
        self._value, self._recipients = value, recipients

    async def run(self, state: StateView) -> StateView:
        state["output"] = self._value
        state["nodes_output"][self.uid] = self._value
        state["messages"].append(ChatMessage(role=Role.ASSISTANT, content=self.uid))
        for uid in self._recipients:
            state["inter_packets"].append(
                SystemPacket(
                    src=ElementAddress(uid=self.uid),
                    dst=ElementAddress(uid=uid),
                    system_event="route",
                )
            )
        return state


class OutputFactory(BaseFactory):
    def accepts(self, cfg, element_type):
        return element_type == "condition_output"

    def create(self, cfg, **dependencies):
        return OutputNode(cfg.value, cfg.recipients)


class OutputSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "condition_output"
    name = "Condition output"
    description = "Produce known state and packet evidence for real condition routing"
    config_schema = OutputConfig
    factory_cls = OutputFactory
    reads = OutputNode.total_reads()
    writes = OutputNode.total_writes()


ELEMENT_SPECIFICATIONS = (
    OutputSpec,
    ThresholdConditionElementSpec,
    RouterDirectConditionElementSpec,
    RouterBooleanConditionElementSpec,
)
