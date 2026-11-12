"""Authoring revisions and view metadata stay outside executable program definitions."""

from enum import StrEnum
from typing import Literal, Self

from pydantic import Field, StrictInt, StrictStr, model_validator

from lumora.elements.construction.snapshots import ResourceSelection
from lumora.models import Model
from lumora.programs.domain.interfaces import ProgramInterface
from lumora.programs.domain.models import BodyPath, ProgramDefinition, ProgramKind, ProgramRef


class CanvasPosition(Model):
    x: float = Field(allow_inf_nan=False)
    y: float = Field(allow_inf_nan=False)


class ProgramPresentation(Model):
    positions: dict[str, CanvasPosition] = Field(default_factory=dict, max_length=10_000)


class ProgramDraft(Model):
    definition: ProgramDefinition
    version: int = Field(ge=1)
    presentation: ProgramPresentation = Field(default_factory=ProgramPresentation)


class ProgramResourceSelection(ResourceSelection):
    """Capture into a graph resource scope or a coordinator configuration field."""

    body_path: BodyPath = ()
    configuration_path: tuple[StrictStr | StrictInt, ...] | None = Field(default=None, max_length=64)


class SaveProgramDraft(Model):
    definition: ProgramDefinition
    expected_version: int = Field(ge=0)
    presentation: ProgramPresentation | None = None
    resource_selections: tuple[ProgramResourceSelection, ...] = Field(default=(), max_length=1000)


class ObservedProgramVersion(Model):
    expected_version: int = Field(ge=1)


class ProgramIssueCode(StrEnum):
    BINDING = "INVALID_BINDING"
    TOPOLOGY = "INVALID_TOPOLOGY"
    CONFIGURATION = "INVALID_CONFIGURATION"
    CONSTRUCTION = "INVALID_CONSTRUCTION"
    REFERENCE = "INVALID_PROGRAM_REFERENCE"


class ProgramIssue(Model):
    code: ProgramIssueCode
    message: str
    path: tuple[str | int, ...] = ()
    severity: Literal["error"] = "error"


class ProgramInterfacePreview(Model):
    """Pure configuration resolution; not publication or execution readiness."""

    interface: ProgramInterface | None = None
    issues: tuple[ProgramIssue, ...] = ()


class ProgramValidation(Model):
    """Publication readiness for one observed draft, not execution admission."""

    version: int = Field(ge=1)
    issues: tuple[ProgramIssue, ...] = ()
    valid: bool = Field(default=True, json_schema_extra={"readOnly": True})

    @model_validator(mode="after")
    def readiness(self) -> Self:
        object.__setattr__(self, "valid", not self.issues)
        return self


class ProgramSummary(Model):
    program_id: str
    name: str
    kind: ProgramKind
    draft_version: int = Field(ge=1)


class ProgramPage(Model):
    programs: tuple[ProgramSummary, ...]
    next_cursor: str | None = None


class RevisionSummary(Model):
    program: ProgramRef
    content_digest: str


class RevisionPage(Model):
    revisions: tuple[RevisionSummary, ...]
    next_cursor: int | None = None


class ProgramConflict(ValueError):
    """An authoring command no longer matches the user's observed draft."""


class ProgramStorageError(RuntimeError):
    """A safe application-owned storage error; no driver diagnostics cross the port."""
