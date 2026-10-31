"""Native async Mongo storage for drafts and append-only published revisions."""

from mas.programs.models import ProgramDefinition, ProgramRef, ProgramRevision
from mas.programs.service import ProgramAccessDenied
from pymongo import ReturnDocument
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import DuplicateKeyError


class MongoProgramRepository:
    def __init__(self, database: AsyncDatabase) -> None:
        self._drafts = database.program_drafts
        self._revisions = database.program_revisions
        self._counters = database.program_revision_counters

    async def save_draft(self, definition: ProgramDefinition) -> None:
        owner = {
            "owner_type": definition.owner.type.value,
            "owner_id": definition.owner.id,
        }
        try:
            await self._drafts.update_one(
                {"_id": definition.program_id, **owner},
                {"$set": {**owner, "data": definition.model_dump_json()}},
                upsert=True,
            )
        except DuplicateKeyError as error:
            # The ID exists under another owner; never transfer ownership in a race.
            raise ProgramAccessDenied(definition.program_id) from error

    async def get_draft(self, program_id: str) -> ProgramDefinition:
        document = await self._drafts.find_one({"_id": program_id})
        if document is None:
            raise KeyError(program_id)
        return ProgramDefinition.model_validate_json(document["data"])

    async def publish(self, definition: ProgramDefinition) -> ProgramRevision:
        counter = await self._counters.find_one_and_update(
            {"_id": definition.program_id},
            {"$inc": {"revision": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        revision = ProgramRevision(definition=definition, revision=counter["revision"])
        await self._revisions.insert_one(
            {
                "_id": f"{definition.program_id}:{revision.revision}",
                "program_id": definition.program_id,
                "revision": revision.revision,
                "data": revision.model_dump_json(),
            }
        )
        return ProgramRevision.model_validate_json(revision.model_dump_json())

    async def get_revision(self, reference: ProgramRef) -> ProgramRevision:
        document = await self._revisions.find_one(
            {
                "_id": f"{reference.program_id}:{reference.revision}",
            }
        )
        if document is None:
            raise KeyError(reference.program_id)
        return ProgramRevision.model_validate_json(document["data"])
