"""Atomic draft versions and source-idempotent publication using native async Mongo."""

from typing import Any

from pydantic import ValidationError
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError, PyMongoError
from pymongo.write_concern import WriteConcern

from lumora.programs.authoring import (
    ProgramConflict,
    ProgramDraft,
    ProgramPresentation,
    ProgramStorageError,
)
from lumora.programs.domain.interfaces import ProgramInterface
from lumora.programs.domain.models import ProgramDefinition, ProgramRef, ProgramRevision
from lumora.services.identity.domain import Identity


class MongoProgramRepository:
    def __init__(self, database: AsyncDatabase[dict[str, Any]]) -> None:
        self._drafts = database.get_collection(
            "program_drafts", write_concern=WriteConcern(w="majority")
        )
        self._revisions = database.get_collection(
            "program_revisions", write_concern=WriteConcern(w="majority")
        )
        self._counters = database.get_collection(
            "program_revision_counters", write_concern=WriteConcern(w="majority")
        )

    async def initialize(self) -> None:
        try:
            await self._drafts.create_index([("owner_type", 1), ("owner_id", 1), ("_id", 1)])
            await self._revisions.create_index([("program_id", 1), ("revision", -1)], unique=True)
        except PyMongoError:
            raise ProgramStorageError("Program storage is unavailable") from None

    @staticmethod
    def _draft(document: dict[str, Any]) -> ProgramDraft:
        try:
            draft = ProgramDraft.model_validate_json(document["data"])
            if (
                draft.definition.program_id != document["_id"]
                or draft.version != document["version"]
                or draft.definition.owner.type.value != document["owner_type"]
                or draft.definition.owner.id != document["owner_id"]
            ):
                raise ProgramStorageError("Program draft storage identity is invalid")
            return draft
        except ValidationError, KeyError, TypeError:
            raise ProgramStorageError("Program draft storage is invalid") from None

    @staticmethod
    def _revision(document: dict[str, Any]) -> ProgramRevision:
        try:
            revision = ProgramRevision.model_validate_json(document["data"])
            if (
                revision.definition.program_id != document["program_id"]
                or revision.revision != document["revision"]
                or document["_id"] != f"{document['program_id']}:draft:{document['source_version']}"
            ):
                raise ProgramStorageError("Published program storage identity is invalid")
            return revision
        except ValidationError, KeyError, TypeError:
            raise ProgramStorageError("Published program storage is invalid") from None

    async def save_draft(
        self,
        definition: ProgramDefinition,
        *,
        expected_version: int,
        presentation: ProgramPresentation,
    ) -> ProgramDraft:
        draft = ProgramDraft(
            definition=definition, version=expected_version + 1, presentation=presentation
        )
        document = {
            "_id": definition.program_id,
            "owner_type": definition.owner.type.value,
            "owner_id": definition.owner.id,
            "version": draft.version,
            "data": draft.model_dump_json(),
        }
        try:
            if expected_version == 0:
                await self._drafts.insert_one(document)
            else:
                result = await self._drafts.replace_one(
                    {
                        "_id": definition.program_id,
                        "owner_type": definition.owner.type.value,
                        "owner_id": definition.owner.id,
                        "version": expected_version,
                    },
                    document,
                )
                if result.modified_count != 1:
                    raise ProgramConflict("Program draft changed; reload before saving")
            return draft
        except DuplicateKeyError:
            current = await self.get_draft(definition.program_id)
            if not current.definition.owner.owns(definition.owner):
                raise PermissionError(
                    "Program ownership cannot be changed by saving a draft"
                ) from None
            raise ProgramConflict("Program draft already exists; reload before saving") from None
        except PyMongoError:
            raise ProgramStorageError(
                "Program storage is unavailable; write outcome may be uncertain"
            ) from None

    async def get_draft(self, program_id: str) -> ProgramDraft:
        try:
            document = await self._drafts.find_one({"_id": program_id})
            if document is None:
                raise KeyError(program_id)
            return self._draft(document)
        except PyMongoError:
            raise ProgramStorageError("Program storage is unavailable") from None

    async def list_drafts(self, owner: Identity, *, after: str, limit: int) -> list[ProgramDraft]:
        try:
            return [
                self._draft(document)
                async for document in self._drafts.find(
                    {"owner_type": owner.type.value, "owner_id": owner.id, "_id": {"$gt": after}}
                )
                .sort("_id", 1)
                .limit(limit)
            ]
        except PyMongoError:
            raise ProgramStorageError("Program storage is unavailable") from None

    async def publish(self, draft: ProgramDraft, interface: ProgramInterface) -> ProgramRevision:
        definition = draft.definition
        previous = await self.get_publication(definition.program_id, draft.version)
        if previous is not None:
            return self._same_source(previous, definition, interface)
        identifier = f"{definition.program_id}:draft:{draft.version}"
        try:
            counter = await self._counters.find_one_and_update(
                {"_id": definition.program_id},
                {"$inc": {"revision": 1}},
                upsert=True,
                return_document=ReturnDocument.AFTER,
            )
            assert counter is not None
            revision = ProgramRevision(
                definition=definition, interface=interface, revision=counter["revision"]
            )
            await self._revisions.insert_one(
                {
                    "_id": identifier,
                    "program_id": definition.program_id,
                    "revision": revision.revision,
                    "source_version": draft.version,
                    "data": revision.model_dump_json(),
                }
            )
            return revision
        except DuplicateKeyError:
            existing = await self.get_publication(definition.program_id, draft.version)
            if existing is None:
                raise ProgramStorageError("Program publication cannot be confirmed") from None
            return self._same_source(existing, definition, interface)
        except PyMongoError:
            raise ProgramStorageError(
                "Program publication is uncertain; retry the same source version"
            ) from None

    @staticmethod
    def _same_source(
        revision: ProgramRevision, definition: ProgramDefinition, interface: ProgramInterface
    ) -> ProgramRevision:
        if revision.definition != definition or revision.interface != interface:
            raise ProgramConflict("Publication source does not match its saved draft")
        return revision

    async def get_publication(self, program_id: str, source_version: int) -> ProgramRevision | None:
        try:
            document = await self._revisions.find_one(
                {"_id": f"{program_id}:draft:{source_version}"}
            )
            return self._revision(document) if document is not None else None
        except PyMongoError:
            raise ProgramStorageError("Program storage is unavailable") from None

    async def get_revision(self, reference: ProgramRef) -> ProgramRevision:
        try:
            document = await self._revisions.find_one(
                {"program_id": reference.program_id, "revision": reference.revision}
            )
            if document is None:
                raise KeyError(reference.program_id)
            return self._revision(document)
        except PyMongoError:
            raise ProgramStorageError("Program storage is unavailable") from None

    async def list_revisions(
        self, program_id: str, *, before: int | None, limit: int
    ) -> list[ProgramRevision]:
        query: dict[str, Any] = {"program_id": program_id}
        if before is not None:
            query["revision"] = {"$lt": before}
        try:
            return [
                self._revision(document)
                async for document in self._revisions.find(query).sort("revision", -1).limit(limit)
            ]
        except PyMongoError:
            raise ProgramStorageError("Program storage is unavailable") from None
