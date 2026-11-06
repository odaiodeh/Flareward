"""Conditional value-flow definitions shared by application and native execution tests."""

from mas.core.enums import ResourceCategory
from mas.domain.element_bundles import ResourceDefinition, ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import (
    ApplicationDefinition,
    ConditionalRoute,
    GraphDefinition,
    JoinPolicy,
    LiteralBinding,
    PathBinding,
    ProgramBody,
    ProgramCallStep,
)


def conditional_values(
    *,
    selected: bool = True,
    consume_after_join: bool = False,
    profile: str = "thread",
    join_policy: JoinPolicy = JoinPolicy.ACTIVE,
) -> GraphDefinition:
    body = ProgramBody(
        implementation=ApplicationDefinition(implementation="identity_program", version="1"),
        input_schema={},
        output_schema={},
    )
    condition = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.CONDITION, rid="route"),
        type_key="router_boolean",
        config={"type": "router_boolean", "boolean_value": selected},
    )
    return GraphDefinition(
        steps=(
            ProgramCallStep(uid="route", program=body, inputs=LiteralBinding(value=None)),
            ProgramCallStep(uid="left", program=body, inputs=LiteralBinding(value="left")),
            ProgramCallStep(uid="right", program=body, inputs=LiteralBinding(value="right")),
            ProgramCallStep(
                uid="consume", program=body, inputs=PathBinding(path=("results", "left"))
            ),
            ProgramCallStep(uid="finish", program=body, inputs=LiteralBinding(value="finished")),
        ),
        resources=(condition,),
        conditions=(
            ConditionalRoute(
                source="route",
                condition=condition.key,
                branches={"true": "left", "false": "right"},
                execution=ExecutionSelection(profile=profile),
            ),
        ),
        edges={
            "left": ("consume",),
            "consume": ("finish",),
            "right": ("consume" if consume_after_join else "finish",),
        },
        entry="route",
        exit="finish",
        join_policy=join_policy,
        outputs={"result": PathBinding(path=("results", "finish"))},
    )
