"""Application-owned asynchronous program repository and runtime ports."""

from collections.abc import Awaitable
from typing import Protocol

from pydantic import BaseModel, JsonValue

from mas.domain.element_bundles import ElementBundle
from mas.programs.models import ProgramDefinition, ProgramRef, ProgramRevision


class ProgramRepository(Protocol):
    async def save_draft(self, definition: ProgramDefinition) -> None: ...
    async def get_draft(self, program_id: str) -> ProgramDefinition: ...
    async def publish(self, definition: ProgramDefinition) -> ProgramRevision: ...
    async def get_revision(self, reference: ProgramRef) -> ProgramRevision: ...


class ChildExecution(Protocol):
    @property
    def execution_id(self) -> str: ...
    async def result(self) -> JsonValue: ...
    async def cancel(self) -> None: ...


class ProgramRuntime(Protocol):
    @property
    def execution_id(self) -> str: ...
    async def invoke_element(
        self,
        bundle: ElementBundle,
        inputs: dict[str, JsonValue],
        *,
        key: str,
    ) -> JsonValue: ...
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
