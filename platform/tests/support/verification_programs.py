"""Reusable program definitions without transport, database or execution SDK imports."""

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.executions.domain.preferences import ExecutionSelection
from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    LiteralBinding,
    OperationStep,
    PathBinding,
    ProgramCallStep,
    ProgramRef,
)
from flareward.resources.domain.bundles import ResourceDefinition, ResourceKey
from flareward.resources.domain.categories import ResourceCategory


def verification_resources() -> tuple[ResourceDefinition, ...]:
    provider = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.PROVIDER, rid="verification"),
        type_key="verification_service",
    )
    operations = tuple(
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid=name),
            type_key=type_key,
            config={"service": "$ref:verification"},
        )
        for name, type_key in (
            ("request", "request_verification"),
            ("inspect", "inspect_verification"),
            ("cancel", "cancel_verification"),
        )
    )
    return (provider, *operations)


def verification_wait_definition(
    registry: ElementRegistry, profile: str, *, interval: float = 0.1
) -> ApplicationDefinition:
    resources = verification_resources()
    key = ResourceKey(category=ResourceCategory.OPERATION, rid="inspect")
    bundle = ElementBundleResolver(registry).resolve(key, resources)
    return ApplicationDefinition(
        implementation="await_verification",
        version="1",
        config={
            "inspection": bundle.model_dump(mode="json"),
            "execution": {"profile": profile},
            "poll_interval_seconds": interval,
            "max_polls": 100,
        },
    )


def verification_graph(
    waiter: ProgramRef, profile: str, *, cancel_before_wait: bool = False
) -> GraphDefinition:
    resources = verification_resources()
    requester = ResourceKey(category=ResourceCategory.OPERATION, rid="request")
    graph = GraphDefinition(
        resources=resources[:2],
        steps=(
            OperationStep(
                uid="request",
                element=requester,
                execution=ExecutionSelection(profile=profile),
                inputs={
                    "subject": PathBinding(path=("values", "subject")),
                    "policy": PathBinding(path=("values", "policy")),
                },
                outputs={"values": PathBinding(path=())},
            ),
            ProgramCallStep(
                uid="wait",
                program=waiter,
                inputs={"plan_id": PathBinding(path=("values", "state", "plan", "plan_id"))},
                outputs={"values": PathBinding(path=())},
            ),
        ),
        edges={"request": ("wait",)},
        entry="request",
        exit="wait",
        inputs={"values": PathBinding(path=())},
        outputs={"result": PathBinding(path=("values",))},
    )
    if not cancel_before_wait:
        return graph
    cancel = OperationStep(
        uid="cancel",
        element=resources[3].key,
        execution=ExecutionSelection(profile=profile),
        inputs={"plan_id": PathBinding(path=("values", "state", "plan", "plan_id"))},
        outputs={"values": PathBinding(path=())},
    )
    return graph.model_copy(
        update={
            "resources": (*graph.resources, resources[3]),
            "steps": (graph.steps[0], cancel, graph.steps[1]),
            "edges": {"request": ("cancel",), "cancel": ("wait",)},
        }
    )


def check_resources() -> tuple[ResourceDefinition, ...]:
    return (
        *verification_resources(),
        *(
            ResourceDefinition(
                key=ResourceKey(category=ResourceCategory.OPERATION, rid=name),
                type_key=kind,
                config={"service": "$ref:verification"},
            )
            for name, kind in (
                ("start-check", "start_verification_check"),
                ("refresh-check", "refresh_verification_check"),
            )
        ),
    )


def check_wait_definition(registry: ElementRegistry, profile: str) -> ApplicationDefinition:
    resources = check_resources()
    bundle = ElementBundleResolver(registry).resolve(resources[5].key, resources)
    return ApplicationDefinition(
        implementation="await_check_run",
        version="1",
        config={
            "inspection": bundle.model_dump(mode="json"),
            "execution": {"profile": profile},
            "poll_interval_seconds": 0.2,
            "max_polls": 100,
        },
    )


def check_graph(waiter: ProgramRef, profile: str) -> GraphDefinition:
    resources = check_resources()
    return GraphDefinition(
        resources=(resources[0], resources[1], resources[4]),
        steps=(
            OperationStep(
                uid="request",
                element=resources[1].key,
                execution=ExecutionSelection(profile=profile),
                inputs={
                    "subject": PathBinding(path=("values", "subject")),
                    "policy": PathBinding(path=("values", "policy")),
                },
                outputs={"values": PathBinding(path=())},
            ),
            OperationStep(
                uid="submit",
                element=resources[4].key,
                execution=ExecutionSelection(profile=profile),
                inputs={
                    "plan_id": PathBinding(path=("values", "state", "plan", "plan_id")),
                    "runner": LiteralBinding(value="github@1"),
                },
                outputs={"values": PathBinding(path=())},
            ),
            ProgramCallStep(
                uid="await-check",
                program=waiter,
                inputs={"intent_id": PathBinding(path=("values", "intent_id"))},
                outputs={"values": PathBinding(path=())},
            ),
        ),
        edges={"request": ("submit",), "submit": ("await-check",)},
        entry="request",
        exit="await-check",
        inputs={"values": PathBinding(path=())},
        outputs={"result": PathBinding(path=("values",))},
    )
