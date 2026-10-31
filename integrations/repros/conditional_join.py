"""SDK-only reproduction; works without the experimental active-join extension."""

import operator
from typing import Annotated

from pydantic import Field
from runengine import GraphBuilder
from runengine.adapters.coordination.config import LocalHostConfig
from runengine.bootstrap.hosts import RunHostBuilder
from runengine.programs.graph.models.state import GraphState


class VisitState(GraphState):
    visits: Annotated[list[str], operator.add] = Field(default_factory=list)


def visit(state: VisitState, *, uid: str) -> VisitState:
    return VisitState(visits=[*state.visits, uid])


def choose(state: VisitState, *, outcome: str) -> str:
    return outcome


async def reproduce(outcome: str = "yes") -> dict:
    builder = GraphBuilder(VisitState)
    for uid in ("choose", "yes", "no", "finish"):
        builder.add_node(uid, visit, kwargs={"uid": uid})
    builder.add_conditional_edge(
        "choose", choose, {"yes": "yes", "no": "no"}, kwargs={"outcome": outcome}
    )
    builder.add_edge("yes", "finish").add_edge("no", "finish")
    graph = builder.set_entry("choose").set_exit("finish").compile()
    async with RunHostBuilder.create(LocalHostConfig()) as host:
        handle = await graph.start(VisitState(), host=host)
        result = await handle.result()
        status = await handle.status()
    return {
        "condition_outcome": outcome,
        "phase": status.phase.value,
        "visits": result.final_state.visits,
        "declared_exit_executed": "finish" in result.final_state.visits,
    }
