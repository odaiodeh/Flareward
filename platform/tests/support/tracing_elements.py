"""Deterministic traced application behavior; no engine or telemetry SDK dependencies."""

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict

from flareward.elements.factory import BaseFactory
from flareward.elements.node import BaseNode
from flareward.programs.graph.state.state_view import StateView
from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.tracing import TracingService


class TraceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    fail: bool = False


class TraceNode(BaseNode):
    READS = {"user_prompt"}
    WRITES = {"output"}

    def __init__(self, tracing: TracingService, fail: bool) -> None:
        super().__init__(tracing_service=tracing)
        self._fail = fail

    async def run(self, state: StateView) -> StateView:
        with self._tracing.trace_agent_iteration(1, "deterministic"):
            with self._tracing.trace_llm(
                "fixture", "deterministic", [{"content": state["user_prompt"]}]
            ) as generation:
                await asyncio.sleep(0.05)
                generation.update(
                    output="deterministic response", usage_details={"input": 2, "output": 3}
                )
            with self._tracing.trace_tool("echo", {"text": state["user_prompt"]}) as tool:
                if self._fail:
                    raise ValueError("must-not-appear-in-trace")
                tool.update(output=state["user_prompt"], metadata={"verified": True})
        state["output"] = state["user_prompt"]
        return state


class TraceFactory(BaseFactory):
    def accepts(self, cfg: TraceConfig, element_type: str) -> bool:
        return element_type == "platform_trace"

    def create(self, cfg: TraceConfig, **dependencies: Any) -> TraceNode:
        return TraceNode(dependencies["deps"].tracing_service, cfg.fail)


class TraceSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_trace"
    name = "Traced fixture"
    description = "Nested deterministic observations for native receiver verification"
    config_schema = TraceConfig
    factory_cls = TraceFactory
    reads = TraceNode.total_reads()
    writes = TraceNode.total_writes()


ELEMENT_SPECIFICATIONS = (TraceSpec,)
