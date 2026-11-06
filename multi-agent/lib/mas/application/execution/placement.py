"""Application-owned static placement inspection port."""

from typing import Protocol

from mas.application.execution.ports import ExecutionError
from mas.core.identity import Identity
from mas.domain.execution.models import ExecutionFailure, FailureKind
from mas.domain.execution.placement import GraphPlacementPlan
from mas.domain.execution_preferences import ExecutionProfileCatalog
from mas.domain.programs.models import ProgramDefinition


class GraphPlacementPreviewer(Protocol):
    async def preview(self, definition: ProgramDefinition, caller: Identity) -> GraphPlacementPlan:
        """Validate and inspect static element placements without executing the graph."""
        ...


class ProfileAccess(Protocol):
    def catalog(self, owner: Identity) -> ExecutionProfileCatalog:
        """Return allowed names/default/capabilities, or refuse the owner."""
        ...


class PlacementRefused(ExecutionError):
    def __init__(self, message: str) -> None:
        super().__init__(
            ExecutionFailure(kind=FailureKind.CONTRACT, code="placement_refused", message=message)
        )
