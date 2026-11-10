"""Shared application-only scenarios exercise two purposes under one root approval."""

from lumora.executions.domain.access import WorkflowAccess
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.models import (
    GraphDefinition,
    LiteralBinding,
    OperationStep,
    PathBinding,
    ProgramCallStep,
    ProgramRef,
)
from support.verification_programs import verification_resources


def workflow_requirements() -> tuple[WorkflowAccess, ...]:
    return tuple(
        WorkflowAccess(
            purpose=purpose,
            scope={"policies": ["release@1"], "actions": actions},
            ttl_seconds=60,
            renewable_for_seconds=180,
        )
        for purpose, actions in (
            ("review@1", ["open", "read", "close"]),
            ("verification@1", ["create", "read", "cancel"]),
        )
    )


def review_verification_graph(review: ProgramRef, profile: str) -> GraphDefinition:
    resources = verification_resources()[:2]
    return GraphDefinition(
        resources=resources,
        steps=(
            OperationStep(
                uid="request",
                element=resources[1].key,
                execution=ExecutionSelection(profile=profile),
                inputs={
                    "subject": PathBinding(path=("values", "subject")),
                    "policy": LiteralBinding(value="release@1"),
                },
                outputs={"values": PathBinding(path=())},
            ),
            ProgramCallStep(
                uid="review",
                program=review,
                inputs={"subject": PathBinding(path=("values", "state", "plan", "subject"))},
                outputs={"values": PathBinding(path=())},
            ),
        ),
        edges={"request": ("review",)},
        entry="request",
        exit="review",
        inputs={"values": PathBinding(path=())},
        outputs={"result": PathBinding(path=("values",))},
    )
