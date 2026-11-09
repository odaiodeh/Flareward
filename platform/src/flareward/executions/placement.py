"""Application-owned static placement inspection port."""

from typing import Protocol

from flareward.executions.domain.models import ExecutionFailure, FailureKind
from flareward.executions.domain.placement import GraphPlacementPlan
from flareward.executions.domain.preferences import ExecutionProfileCatalog
from flareward.executions.ports import ExecutionError
from flareward.programs.domain.models import ProgramDefinition
from flareward.services.identity.domain import Identity


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
