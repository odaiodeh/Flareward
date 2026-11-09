"""Shared graph data is independent of engine and transport test harnesses."""

from pydantic import JsonValue

from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import (
    ConditionalRoute,
    ElementStep,
    GraphDefinition,
    GraphWritePolicy,
    PathBinding,
)
from flareward.resources.domain.categories import ResourceCategory
from support.scenarios import resource


def routing_graph(
    type_key: str,
    config: dict[str, JsonValue],
    *,
    profile: str = "thread",
    value: str = "0.75",
    branches: dict[str, str] | None = None,
    recipients: tuple[str, ...] = (),
) -> GraphDefinition:
    outputs = tuple(
        resource(
            uid,
            category=ResourceCategory.NODE,
            type_key="condition_output",
            config={"value": text, "recipients": list(recipients) if uid == "score" else []},
        )
        for uid, text in (("score", value), ("yes", "passed"), ("no", "failed"), ("finish", "done"))
    )
    condition = resource(
        "condition", category=ResourceCategory.CONDITION, type_key=type_key, config=config
    )
    return GraphDefinition(
        write_policy=GraphWritePolicy.REDUCE,
        resources=(*outputs, condition),
        steps=tuple(ElementStep(uid=item.key.rid, element=item.key) for item in outputs),
        edges={"yes": ("finish",), "no": ("finish",)},
        conditions=(
            ConditionalRoute(
                source="score",
                condition=condition.key,
                branches=branches if branches is not None else {"true": "yes", "false": "no"},
                execution=ExecutionSelection(profile=profile),
            ),
        ),
        entry="score",
        exit="finish",
        outputs={
            "steps": PathBinding(path=("nodes_output",)),
            "visits": PathBinding(path=("messages",)),
        },
    )
