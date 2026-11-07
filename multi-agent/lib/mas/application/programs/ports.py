"""Application-owned asynchronous program repository and runtime ports."""

from collections.abc import Awaitable
from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, JsonValue

from mas.application.programs.authoring import ProgramDraft, ProgramPresentation
from mas.core.identity import Identity
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import (
    Bindings,
    ProgramDefinition,
    ProgramRef,
    ProgramRevision,
    Projection,
)


class ProgramRepository(Protocol):
    async def save_draft(
        self,
        definition: ProgramDefinition,
        *,
        expected_version: int,
        presentation: ProgramPresentation,
    ) -> ProgramDraft: ...
    async def get_draft(self, program_id: str) -> ProgramDraft: ...
    async def list_drafts(
        self, owner: Identity, *, after: str, limit: int
    ) -> list[ProgramDraft]: ...
    async def publish(self, draft: ProgramDraft) -> ProgramRevision: ...
    async def get_publication(
        self, program_id: str, source_version: int
    ) -> ProgramRevision | None: ...
    async def list_revisions(
        self, program_id: str, *, before: int | None, limit: int
    ) -> list[ProgramRevision]: ...
    async def get_revision(self, reference: ProgramRef) -> ProgramRevision: ...


class ChildExecution(Protocol):
    @property
    def execution_id(self) -> str: ...
    async def result(self) -> JsonValue: ...
    async def cancel(self) -> None: ...


@dataclass(frozen=True)
class ChildContract:
    """Declared request projection and consumed results of one backend child alias."""

    inputs: Projection | None = None
    scope_schema: dict[str, JsonValue] | None = None
    outputs: Bindings = field(default_factory=dict)
    result_model: type[BaseModel] | None = None


@runtime_checkable
class ChildContracts(Protocol):
    """Optional configuration interface; absent scope schemas use Program input."""

    def child_contracts(self) -> dict[str, ChildContract]: ...


class ElementCalls(Protocol):
    """The element-call portion of a Program runtime, without coordination methods."""

    async def invoke_element(
        self,
        bundle: ElementBundle,
        inputs: JsonValue,
        *,
        key: str,
        execution: ExecutionSelection | None = None,
    ) -> JsonValue:
        """Invoke a configured element; operations return their typed JSON result."""
        ...


class ProgramRuntime(ElementCalls, Protocol):
    @property
    def execution_id(self) -> str: ...

    async def start_child(
        self,
        name: str,
        inputs: JsonValue,
        *,
        key: str,
        environment_imports: dict[str, str] | None = None,
    ) -> ChildExecution: ...
    async def receive(self, name: str, *, timeout: float | None = None) -> JsonValue: ...
    async def sleep(self, seconds: float) -> None: ...


class ApplicationProgram(Protocol):
    def __call__(
        self,
        runtime: ProgramRuntime,
        inputs: JsonValue,
        config: BaseModel,
    ) -> Awaitable[JsonValue]: ...
