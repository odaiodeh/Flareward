"""Shared program persistence contracts; no concrete database or execution host."""

import asyncio

import pytest
from pydantic import ValidationError

from lumora.programs.authoring import CanvasPosition, ProgramConflict, ProgramPresentation
from lumora.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    ProgramDefinition,
)
from lumora.programs.ports import ProgramRepository
from lumora.services.identity.domain import Identity


def definition(program_id: str, owner: Identity | None = None) -> ProgramDefinition:
    return ProgramDefinition(
        program_id=program_id,
        name=program_id,
        owner=owner or Identity.user("same-id"),
        implementation=ApplicationDefinition(implementation="greeting", version="1"),
    )


async def assert_owner_scoped_pages(repository: ProgramRepository) -> None:
    owner = Identity.user("same-id")
    for program_id, identity in (
        ("a", owner),
        ("b", Identity.team("same-id")),
        ("c", owner),
        ("d", Identity.user("other")),
    ):
        await repository.save_draft(
            definition(program_id, identity), expected_version=0, presentation=ProgramPresentation()
        )
    first = await repository.list_drafts(owner, after="", limit=1)
    assert [value.definition.program_id for value in first] == ["a"]
    second = await repository.list_drafts(owner, after="a", limit=1)
    assert [value.definition.program_id for value in second] == ["c"]
    assert await repository.list_drafts(owner, after="c", limit=10) == []
    first[0].definition.input_schema["description"] = "local mutation"
    assert "description" not in (await repository.get_draft("a")).definition.input_schema


async def assert_atomic_edits(repository: ProgramRepository) -> None:
    original = definition("edit")
    presentation = ProgramPresentation(positions={"step": CanvasPosition(x=10, y=20)})
    saved = await repository.save_draft(original, expected_version=0, presentation=presentation)
    saved.definition.input_schema["description"] = "reader mutation"
    presentation.positions.clear()
    loaded = await repository.get_draft("edit")
    assert loaded.version == 1 and loaded.presentation.positions["step"].x == 10
    assert "description" not in loaded.definition.input_schema
    contenders = await asyncio.gather(
        *(
            repository.save_draft(
                original.model_copy(update={"name": f"Editor {index}"}),
                expected_version=loaded.version,
                presentation=loaded.presentation,
            )
            for index in range(5)
        ),
        return_exceptions=True,
    )
    winners = [value for value in contenders if not isinstance(value, BaseException)]
    assert len(winners) == 1 and winners[0].version == 2
    assert sum(isinstance(value, ProgramConflict) for value in contenders) == 4
    assert (await repository.get_draft("edit")).definition.name == winners[0].definition.name
    with pytest.raises(ProgramConflict):
        await repository.save_draft(original, expected_version=0, presentation=loaded.presentation)
    with pytest.raises(PermissionError):
        await repository.save_draft(
            original.model_copy(update={"owner": Identity.team("same-id")}),
            expected_version=0,
            presentation=loaded.presentation,
        )


async def assert_source_idempotent_publication(repository: ProgramRepository) -> None:
    original = definition("publish")
    draft = await repository.save_draft(
        original, expected_version=0, presentation=ProgramPresentation()
    )
    publications = await asyncio.gather(*(repository.publish(draft) for _ in range(8)))
    first = publications[0]
    assert all(value == first for value in publications)
    edited = await repository.save_draft(
        original.model_copy(update={"name": "New name"}),
        expected_version=draft.version,
        presentation=ProgramPresentation(),
    )
    second = await repository.publish(edited)
    assert second.revision > first.revision
    assert await repository.get_publication("publish", draft.version) == first
    assert await repository.publish(draft) == first
    assert [
        value.reference
        for value in await repository.list_revisions("publish", before=None, limit=1)
    ] == [second.reference]
    assert [
        value.reference
        for value in await repository.list_revisions("publish", before=second.revision, limit=1)
    ] == [first.reference]
    assert await repository.list_revisions("publish", before=first.revision, limit=1) == []
    first.definition.input_schema["description"] = "reader mutation"
    assert (
        "description"
        not in (await repository.get_revision(first.reference)).definition.input_schema
    )
    with pytest.raises(ProgramConflict):
        await repository.publish(draft.model_copy(update={"definition": edited.definition}))


async def assert_unfinished_drafts_cannot_become_revisions(repository: ProgramRepository) -> None:
    original = definition("unfinished").model_copy(
        update={"implementation": GraphDefinition(steps=())}
    )
    draft = await repository.save_draft(
        original, expected_version=0, presentation=ProgramPresentation()
    )
    assert await repository.get_draft(original.program_id) == draft
    assert (await repository.list_drafts(original.owner, after="", limit=1)) == [draft]
    with pytest.raises(ValidationError, match="entry and exit"):
        await repository.publish(draft)
    assert await repository.get_publication(original.program_id, draft.version) is None
    assert not await repository.list_revisions(original.program_id, before=None, limit=10)


PROGRAM_STORE_CONTRACTS = (
    assert_owner_scoped_pages,
    assert_atomic_edits,
    assert_source_idempotent_publication,
    assert_unfinished_drafts_cannot_become_revisions,
)
