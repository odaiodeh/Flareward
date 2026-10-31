"""Snapshot storage; no mutable domain object is retained or shared with a reader."""

import asyncio

from mas.programs.models import ProgramDefinition, ProgramRef, ProgramRevision


class MemoryProgramRepository:
    def __init__(self) -> None:
        self._drafts: dict[str, str] = {}
        self._revisions: dict[tuple[str, int], str] = {}
        self._lock = asyncio.Lock()

    async def save_draft(self, definition: ProgramDefinition) -> None:
        async with self._lock:
            previous = self._drafts.get(definition.program_id)
            if previous is not None:
                owner = ProgramDefinition.model_validate_json(previous).owner
                if not owner.owns(definition.owner):
                    raise PermissionError("Program ownership cannot be changed by saving a draft")
            self._drafts[definition.program_id] = definition.model_dump_json()

    async def get_draft(self, program_id: str) -> ProgramDefinition:
        return ProgramDefinition.model_validate_json(self._drafts[program_id])

    async def publish(self, definition: ProgramDefinition) -> ProgramRevision:
        async with self._lock:
            number = 1 + max(
                (
                    revision
                    for identity, revision in self._revisions
                    if identity == definition.program_id
                ),
                default=0,
            )
            revision = ProgramRevision(definition=definition, revision=number)
            self._revisions[definition.program_id, number] = revision.model_dump_json()
            return ProgramRevision.model_validate_json(revision.model_dump_json())

    async def get_revision(self, reference: ProgramRef) -> ProgramRevision:
        return ProgramRevision.model_validate_json(
            self._revisions[reference.program_id, reference.revision]
        )
