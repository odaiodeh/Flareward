"""Authoring policy uses storage ports and installed schemas without a database or server."""

from unittest.mock import create_autospec

import pytest
from pydantic import BaseModel, ConfigDict, SecretStr
from support.secrets import MemorySecretStore

from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.contracts import BlueprintAuthoringRepository, BlueprintDocument
from lumora.programs.templates.exceptions import BlueprintConflictError, InvalidMetadataKeysError
from lumora.programs.templates.models.prompt_shortcuts import PromptShortcuts
from lumora.resources.domain.references import NodeRef
from lumora.services.identity.domain import Identity


class AuthoringDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    node: NodeRef | None = None
    credential: SecretStr | None = None
    prompt_shortcuts: PromptShortcuts | None = None


@pytest.fixture
def authoring_case(application):
    repository = create_autospec(BlueprintAuthoringRepository, instance=True)
    secrets = MemorySecretStore()
    service = BlueprintAuthoringService(
        repository, AuthoringDraft, ConfigurationSecrets(application.elements, secrets)
    )
    repository.get.return_value = BlueprintDocument(
        blueprint_id="draft",
        identity=application.owner,
        spec_dict={"name": "Original", "prompt_shortcuts": [{"id": "12345678", "text": "Run"}]},
        metadata={"keep": True},
        version=3,
    )
    repository.replace.return_value = True
    return service, repository, secrets


async def test_create_protects_private_values_and_collects_typed_references(
    application, authoring_case
):
    service, repository, secrets = authoring_case
    created = await service.create(
        {"name": "New", "credential": "private-value", "node": "$ref:catalog-node"},
        application.owner,
    )
    assert created.version == 1 and created.rid_refs == ["catalog-node"]
    assert "private-value" not in created.model_dump_json()
    assert (
        await secrets.get(application.owner, created.spec_dict["credential"])
    ).get_secret_value() == "private-value"
    repository.create.assert_awaited_once_with(created)


async def test_update_preserves_omitted_shortcuts_and_metadata(application, authoring_case):
    service, repository, _ = authoring_case
    previous = repository.get.return_value.model_copy(deep=True)
    updated = await service.update(
        "draft", {"name": "Edited"}, application.owner, expected_version=3
    )
    assert (
        updated.version == 4
        and updated.spec_dict["prompt_shortcuts"] == previous.spec_dict["prompt_shortcuts"]
    )
    assert updated.metadata == previous.metadata and repository.get.return_value == previous
    repository.replace.assert_awaited_once_with(previous, updated)


async def test_stale_edits_and_concurrent_replacements_are_rejected(application, authoring_case):
    service, repository, _ = authoring_case
    with pytest.raises(BlueprintConflictError):
        await service.update("draft", {"name": "Stale"}, application.owner, expected_version=2)
    repository.replace.assert_not_awaited()
    repository.replace.return_value = False
    with pytest.raises(BlueprintConflictError):
        await service.set_metadata("draft", {"added": True}, application.owner)


async def test_ownership_guards_every_read_and_write_before_parsing(authoring_case):
    service, repository, _ = authoring_case
    other = Identity.user("other")
    for operation in (
        service.get("draft", other),
        service.update("draft", {"invalid-private-input": True}, other),
        service.delete("draft", other),
        service.set_metadata("draft", {"bad.key": True}, other),
        service.set_shortcuts("draft", [{"bad": "value"}], other),
    ):
        with pytest.raises(PermissionError):
            await operation
    repository.replace.assert_not_awaited()
    repository.delete.assert_not_awaited()


async def test_invalid_configuration_does_not_echo_private_values(application, authoring_case):
    service, repository, _ = authoring_case
    with pytest.raises(ValueError) as raised:
        await service.create(
            {"name": "Invalid", "credential": {"value": "private-value"}}, application.owner
        )
    assert "private-value" not in str(raised.value)
    repository.create.assert_not_awaited()


@pytest.mark.parametrize("key", ["bad.key", "$operator", "safe\n"])
async def test_metadata_rejects_unsafe_keys(application, authoring_case, key):
    service, repository, _ = authoring_case
    with pytest.raises(InvalidMetadataKeysError):
        await service.set_metadata("draft", {key: "value"}, application.owner)
    repository.replace.assert_not_awaited()
