"""Snapshot storage; no mutable domain object is retained or shared with a reader."""

import asyncio

from flareward.programs.authoring import ProgramConflict, ProgramDraft, ProgramPresentation
from flareward.programs.domain.models import ProgramDefinition, ProgramRef, ProgramRevision
from flareward.services.identity.domain import Identity


class MemoryProgramRepository:
    def __init__(self) -> None:
        self._drafts: dict[str, str] = {}
        self._revisions: dict[tuple[str, int], str] = {}
        self._publications: dict[tuple[str, int], int] = {}
        self._lock = asyncio.Lock()

    async def save_draft(
        self,
        definition: ProgramDefinition,
        *,
        expected_version: int,
        presentation: ProgramPresentation,
    ) -> ProgramDraft:
        async with self._lock:
            previous = self._drafts.get(definition.program_id)
            if previous is not None:
                draft = ProgramDraft.model_validate_json(previous)
                owner = draft.definition.owner
                if not owner.owns(definition.owner):
                    raise PermissionError("Program ownership cannot be changed by saving a draft")
                if draft.version != expected_version:
                    raise ProgramConflict("Program draft changed; reload before saving")
            elif expected_version != 0:
                raise ProgramConflict("Program draft no longer exists")
            updated = ProgramDraft(
                definition=definition, version=expected_version + 1, presentation=presentation
            )
            self._drafts[definition.program_id] = updated.model_dump_json()
            return ProgramDraft.model_validate_json(updated.model_dump_json())

    async def get_draft(self, program_id: str) -> ProgramDraft:
        return ProgramDraft.model_validate_json(self._drafts[program_id])

    async def list_drafts(self, owner: Identity, *, after: str, limit: int) -> list[ProgramDraft]:
        drafts = (
            ProgramDraft.model_validate_json(value)
            for key, value in sorted(self._drafts.items())
            if key > after
        )
        return [draft for draft in drafts if draft.definition.owner.owns(owner)][:limit]

    async def publish(self, draft: ProgramDraft) -> ProgramRevision:
        async with self._lock:
            definition = draft.definition
            source = definition.program_id, draft.version
            if source in self._publications:
                existing_number = self._publications[source]
                published = ProgramRevision.model_validate_json(
                    self._revisions[definition.program_id, existing_number]
                )
                if published.definition != definition:
                    raise ProgramConflict("Publication source does not match its saved draft")
                return published
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
            self._publications[source] = number
            return ProgramRevision.model_validate_json(revision.model_dump_json())

    async def get_revision(self, reference: ProgramRef) -> ProgramRevision:
        return ProgramRevision.model_validate_json(
            self._revisions[reference.program_id, reference.revision]
        )

    async def get_publication(self, program_id: str, source_version: int) -> ProgramRevision | None:
        revision = self._publications.get((program_id, source_version))
        return (
            await self.get_revision(ProgramRef(program_id=program_id, revision=revision))
            if revision is not None
            else None
        )

    async def list_revisions(
        self, program_id: str, *, before: int | None, limit: int
    ) -> list[ProgramRevision]:
        return [
            ProgramRevision.model_validate_json(value)
            for (identity, number), value in sorted(self._revisions.items(), reverse=True)
            if identity == program_id and (before is None or number < before)
        ][:limit]
