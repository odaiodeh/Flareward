"""Human Review uses the same resources, bundles and nested calls as any program."""

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.construction.resolver import ElementBundleResolver
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ProgramRef,
)
from lumora.resources.domain.bundles import ElementBundle, ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from lumora.services.reviews.domain.results import HumanReviewResult
from support.reviews import review_request


def review_resources() -> tuple[ResourceDefinition, ...]:
    return (
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.PROVIDER, rid="review"),
            type_key="review_service",
        ),
        *(
            ResourceDefinition(
                key=ResourceKey(category=ResourceCategory.OPERATION, rid=name),
                type_key=kind,
                config={"service": "$ref:review"},
            )
            for name, kind in (
                ("open", "open_human_review"),
                ("inspect", "inspect_human_review"),
                ("confirm", "confirm_human_review"),
            )
        ),
    )


def review_definition(
    registry: ElementRegistry, profile: str = "thread", *, timeout_seconds: int = 60
) -> CustomCoordinatorDefinition:
    resources = review_resources()
    resolver = ElementBundleResolver(registry)
    return CustomCoordinatorDefinition(
        implementation="human_review",
        version="1",
        config={
            "policy": "release@1",
            "template": review_request()
            .specification.model_copy(update={"timeout_seconds": timeout_seconds})
            .model_dump(mode="json", exclude={"subject"}),
            "opener": resolver.resolve(resources[1].key, resources).model_dump(mode="json"),
            "inspection": resolver.resolve(resources[2].key, resources).model_dump(mode="json"),
            "execution": {"profile": profile},
            "reconcile_seconds": 0.2,
            "max_checks": timeout_seconds * 5,
        },
    )


def review_graph(review: ProgramRef) -> GraphDefinition:
    return GraphDefinition(
        steps=(
            ProgramCallStep(
                uid="review",
                program=review,
                inputs={"subject": PathBinding(path=("values", "subject"))},
                outputs={"values": PathBinding(path=())},
            ),
        ),
        entry="review",
        exit="review",
        inputs={"values": PathBinding(path=())},
        outputs={"result": PathBinding(path=("values",))},
    )


def review_body(
    registry: ElementRegistry, profile: str = "thread", *, timeout_seconds: int = 60
) -> ProgramBody:
    return ProgramBody(
        implementation=review_definition(registry, profile, timeout_seconds=timeout_seconds),
        output_schema=HumanReviewResult.model_json_schema(),
    )


def confirmation_bundle(registry: ElementRegistry) -> ElementBundle:
    resources = review_resources()
    return ElementBundleResolver(registry).resolve(resources[3].key, resources)
