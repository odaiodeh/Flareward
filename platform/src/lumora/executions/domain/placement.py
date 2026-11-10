"""Safe placement values; concrete backend configuration remains private."""

from enum import StrEnum
from typing import Literal

from lumora.models import Model
from lumora.programs.domain.models import BodyPath, ProgramRef
from lumora.resources.domain.categories import ResourceCategory


class PlacementScope(StrEnum):
    INVOCATION = "invocation"
    RUN = "run"


class InvocationPlacement(Model):
    step_uid: str
    category: Literal[ResourceCategory.NODE, ResourceCategory.CONDITION, ResourceCategory.OPERATION]
    profile: str
    environment: str | None = None
    binding_scope: PlacementScope = PlacementScope.INVOCATION


class GraphPlacementPlan(Model):
    default_profile: str
    invocations: tuple[InvocationPlacement, ...]
    environments: dict[str, str]


class PreparedInvocationPlacement(Model):
    """Static authored selection; imported environment profiles resolve in the parent."""

    step_uid: str
    category: Literal[ResourceCategory.NODE, ResourceCategory.CONDITION, ResourceCategory.OPERATION]
    profile: str | None = None
    environment: str | None = None


class PreparedChildPlacement(Model):
    environment_imports: dict[str, str]
    program: PreparedProgramPlacement


class PreparedProgramPlacement(Model):
    """Safe frozen intent; dynamic calls remain observable only when executed."""

    program: ProgramRef
    body_path: BodyPath = ()
    default_profile: str
    environments: dict[str, str]
    imported_environments: tuple[str, ...] = ()
    invocations: tuple[PreparedInvocationPlacement, ...] = ()
    children: dict[str, PreparedChildPlacement] = {}
    dynamic_invocations: bool = False
