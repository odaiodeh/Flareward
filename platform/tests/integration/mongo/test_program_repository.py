"""Real Mongo program authoring, publication and corrupt-storage boundaries."""

import pytest
from support.program_authoring import assert_unfinished_program_lifecycle
from support.program_interfaces import declared_interface
from support.program_store_contracts import PROGRAM_STORE_CONTRACTS, definition
from support.server import api_process

from lumora.programs.adapters.mongo.program_repository import MongoProgramRepository
from lumora.programs.authoring import ProgramPresentation, ProgramStorageError
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize("profile", ["thread", "process"])
async def test_native_authoring_can_reopen_validate_complete_and_execute_a_draft(
    secret_settings, mongo_database, tmp_path, profile
):
    settings = secret_settings.model_copy(update={"element_modules": ("support.elements",)})
    async with api_process(settings, tmp_path / "api.log") as http:
        await assert_unfinished_program_lifecycle(http, Identity.user("owner"), profile=profile)
    assert await mongo_database.program_executions.count_documents({"_id": "refused"}) == 0


@pytest.mark.parametrize("contract", PROGRAM_STORE_CONTRACTS)
async def test_mongo_program_repository(mongo_database, contract):
    repository = MongoProgramRepository(mongo_database)
    await repository.initialize()
    await contract(repository)


async def test_mongo_program_storage_rejects_mismatched_snapshot_identity(mongo_database):
    repository = MongoProgramRepository(mongo_database)
    await repository.initialize()
    draft = await repository.save_draft(
        definition("corrupt"), expected_version=0, presentation=ProgramPresentation()
    )
    published = await repository.publish(draft, interface=declared_interface((draft).definition))
    await mongo_database.program_drafts.update_one(
        {"_id": "corrupt"}, {"$set": {"owner_id": "different-owner"}}
    )
    with pytest.raises(ProgramStorageError, match="storage identity"):
        await repository.get_draft("corrupt")
    await mongo_database.program_revisions.update_one(
        {"program_id": "corrupt"}, {"$set": {"source_version": 2}}
    )
    with pytest.raises(ProgramStorageError, match="storage identity"):
        await repository.get_revision(published.reference)
