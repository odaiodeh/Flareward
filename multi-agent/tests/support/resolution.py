"""Resolved blueprint fixtures use application contracts without vendor schemas."""

from collections.abc import Iterable
from types import SimpleNamespace

from mas.blueprints.contracts import BlueprintResolution
from mas.core.element_meta import ElementConfigMeta
from mas.core.enums import ResourceCategory
from mas.core.resource_models import ResourceSpec, StepDef


def resolve_configurations(
    configurations: tuple[ElementConfigMeta, ...],
    missing: dict[str, str] | None = None,
    *,
    plan: Iterable[StepDef] = (),
) -> BlueprintResolution:
    collections = {category.value: [] for category in ResourceCategory}
    for meta in configurations:
        collections[meta.category.value].append(
            ResourceSpec[type(meta.config)](
                rid=meta.rid, name=meta.name, type=meta.type_key, config=meta.config
            )
        )
    return BlueprintResolution(
        SimpleNamespace(
            **collections,
            plan=tuple(plan),
            name="Inspection",
            description="",
            execution_profile=None,
            environments={},
        ),
        missing or {},
    )
