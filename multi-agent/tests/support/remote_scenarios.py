"""Program definitions for remote scenarios contain only application contracts."""

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.core.enums import ResourceCategory
from mas.domain.element_bundles import ElementBundle, ResourceKey
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import (
    ElementStep,
    GraphDefinition,
    PathBinding,
    ProgramCallStep,
    ProgramRef,
)

from support.elements import DependencySpec
from support.remote import RemoteOperationSpec
from support.scenarios import resource


def remote_operation_bundle() -> ElementBundle:
    registry = ElementRegistry()
    registry.register_spec_class(RemoteOperationSpec)
    registry.register_spec_class(DependencySpec)
    resources = list(remote_graph().resources)
    resources[0] = resources[0].model_copy(
        update={
            "key": ResourceKey(category=ResourceCategory.OPERATION, rid="probe"),
            "type_key": RemoteOperationSpec.type_key,
        }
    )
    return ElementBundleResolver(registry).resolve(resources[0].key, resources)


def remote_graph(*, retained: bool = False, fail: bool = False) -> GraphDefinition:
    node = resource(
        "probe",
        category=ResourceCategory.NODE,
        type_key="platform_remote",
        config={"dependency": "$ref:middle", "fail": fail},
    )
    selection = (
        ExecutionSelection(environment="shared")
        if retained
        else ExecutionSelection(profile="remote")
    )
    return GraphDefinition(
        steps=tuple(
            ElementStep(uid=uid, element=node.key, execution=selection)
            for uid in ("first", "second", "third")
        ),
        resources=(
            node,
            resource("middle", config={"value": "middle", "dependency": "$ref:leaf"}),
            resource("leaf", config={"value": "leaf"}),
        ),
        edges={"first": ("second",), "second": ("third",)},
        entry="first",
        exit="third",
        environments={"shared": "remote"} if retained else {},
        inputs={"user_prompt": PathBinding(path=("name",))},
        outputs={"proofs": PathBinding(path=("nodes_output",))},
    )


def borrowing_graph(child: ProgramRef) -> GraphDefinition:
    base = remote_graph(retained=True)
    return GraphDefinition(
        steps=(
            base.steps[0].model_copy(update={"uid": "before"}),
            ProgramCallStep(
                uid="child",
                program=child,
                inputs={"name": PathBinding(path=("user_prompt",))},
                outputs={"nodes_output": PathBinding(path=("proofs",))},
                environment_imports={"shared": "shared"},
            ),
            base.steps[-1].model_copy(update={"uid": "after"}),
        ),
        resources=base.resources,
        edges={"before": ("child",), "child": ("after",)},
        entry="before",
        exit="after",
        environments=base.environments,
        inputs=base.inputs,
        outputs=base.outputs,
    )


def scoped_environment_graph(child: ProgramRef, waiting: ProgramRef) -> GraphDefinition:
    """The child owns a short reuse scope while the parent can continue afterward."""
    return GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="scoped",
                program=child,
                inputs={"name": PathBinding(path=("user_prompt",))},
                outputs={"nodes_output": PathBinding(path=("proofs",))},
            ),
            ProgramCallStep(
                uid="wait",
                program=waiting,
                outputs={"output": PathBinding(path=("answer",))},
            ),
        ),
        edges={"scoped": ("wait",)},
        entry="scoped",
        exit="wait",
        inputs={"user_prompt": PathBinding(path=("name",))},
        outputs={
            "proofs": PathBinding(path=("nodes_output",)),
            "answer": PathBinding(path=("output",)),
        },
    )
