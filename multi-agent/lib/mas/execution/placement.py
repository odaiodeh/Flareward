"""Safe placement inspection contracts; backend configuration remains private."""

from enum import StrEnum
from typing import Literal, Protocol

from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.programs.models import Model, ProgramDefinition


class PlacementScope(StrEnum):
    INVOCATION = "invocation"
    RUN = "run"


class InvocationPlacement(Model):
    step_uid: str
    category: Literal[ResourceCategory.NODE, ResourceCategory.CONDITION]
    profile: str
    environment: str | None = None
    binding_scope: PlacementScope = PlacementScope.INVOCATION


class GraphPlacementPlan(Model):
    default_profile: str
    invocations: tuple[InvocationPlacement, ...]
    environments: dict[str, str]


class GraphPlacementPreviewer(Protocol):
    async def preview(self, definition: ProgramDefinition, caller: Identity) -> GraphPlacementPlan:
        """Validate and inspect static element placements without executing the graph."""
        ...
