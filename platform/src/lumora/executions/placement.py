"""Application-owned static placement inspection port."""

from typing import Protocol

from lumora.executions.domain.models import ExecutionFailure, FailureKind
from lumora.executions.domain.placement import GraphPlacementPlan
from lumora.executions.domain.preferences import ExecutionProfileCatalog
from lumora.executions.ports import ExecutionError
from lumora.programs.domain.models import ProgramDefinition
from lumora.services.identity.domain import Identity


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
