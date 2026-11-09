"""Caller configuration shares resource policy and keeps optimistic writes behind a port."""

from unittest.mock import create_autospec

import pytest
from pydantic import BaseModel, Field, SecretStr
from support.secrets import MemoryCipher

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.hints import ReadOnlyHint
from flareward.resources.authoring import (
    BuiltinConfigurationRepository,
    ResourceAuthoringRepository,
    ResourceAuthoringService,
    ResourceRecord,
)
from flareward.resources.domain.builtins import BuiltinResourceDescriptor
from flareward.resources.domain.models import Resource
from flareward.resources.errors import ResourceConflictError
from flareward.resources.field_encryption import ResourceFieldEncryption
from flareward.services.identity.domain import Identity


class Configuration(BaseModel):
    token: SecretStr = Field(
        alias="apiKey", json_schema_extra=ReadOnlyHint(read_only=False).to_hints()
    )
    label: str = Field(
        default="Default", json_schema_extra=ReadOnlyHint(read_only=False).to_hints()
    )
    fixed: str = "Shared"


@pytest.fixture
def builtin_case(application):
    elements = create_autospec(ElementRegistry, instance=True)
    elements.get_schema.return_value = Configuration
    elements.get_spec.return_value.version = "1.0.0"
    cipher = MemoryCipher()
    fields = ResourceFieldEncryption(elements, cipher)
    repository = create_autospec(ResourceAuthoringRepository, instance=True)
    repository.get.return_value = ResourceRecord(
        resource=Resource(
            rid="builtin",
            identity=Identity.user("admin"),
            category="tools",
            type="fixture",
            name="Shared",
            cfg_dict=fields.encrypt_model(Configuration(apiKey="admin-private")),
        ),
        descriptor=BuiltinResourceDescriptor(rid="builtin", visibility="public"),
    )
    overlays = create_autospec(BuiltinConfigurationRepository, instance=True)
    overlays.get.return_value = None
    overlays.replace.return_value = True
    return (
        ResourceAuthoringService(repository, elements, fields, overlays),
        repository,
        overlays,
        cipher,
    )


async def test_configuration_encrypts_alias_values_merges_edits_and_projects_owned_fields(
    application, builtin_case
):
    service, repository, overlays, cipher = builtin_case
    owner = application.owner
    first = await service.configure(
        "builtin", owner, config={"apiKey": "caller-private"}, expected_version=0
    )
    assert first.version == 1 and "caller-private" not in first.model_dump_json()
    assert cipher.decrypt(first.fields["token"]) == "caller-private"
    overlays.replace.assert_awaited_once_with(None, first)
    overlays.get.return_value = first
    second = await service.configure(
        "builtin", owner, config={"label": "Personal"}, expected_version=1
    )
    assert second.version == 2 and second.fields["label"] == "Personal"
    assert cipher.decrypt(second.fields["token"]) == "caller-private"
    assert first.version == 1 and "label" not in first.fields
    overlays.get.return_value = second
    projected = await service.get("builtin", owner)
    assert projected.user_configured and projected.cfg_dict["token"] == second.fields["token"]
    assert "admin-private" not in projected.model_dump_json()
    assert (await service.configuration("builtin", owner)) == second
    assert repository.get.return_value.resource.version == 1


async def test_configuration_guards_visibility_readonly_fields_and_conflicting_writes(
    application, builtin_case
):
    service, repository, overlays, _ = builtin_case
    owner = application.owner
    for config in (
        {"fixed": "private"},
        {"token": {"invalid": "private"}},
        {"apiKey": "private", "token": "other-private"},
    ):
        with pytest.raises(ValueError) as raised:
            await service.configure("builtin", owner, config=config)
        assert "private" not in str(raised.value)
    with pytest.raises(ResourceConflictError):
        await service.configure("builtin", owner, config={"token": "private"}, expected_version=2)
    overlays.replace.assert_not_awaited()
    overlays.replace.return_value = False
    with pytest.raises(ResourceConflictError):
        await service.configure("builtin", owner, config={"token": "private"})
    repository.get.return_value.descriptor.visibility = "draft"
    with pytest.raises(KeyError):
        await service.configuration("builtin", owner)
    with pytest.raises(KeyError):
        await service.reset_configuration("builtin", owner)


async def test_reset_keeps_version_fence_and_reports_cleared_configuration(
    application, builtin_case
):
    service, _, overlays, _ = builtin_case
    first = await service.configure("builtin", application.owner, config={"token": "private"})
    overlays.get.return_value = first
    await service.reset_configuration("builtin", application.owner, expected_version=1)
    cleared = overlays.replace.call_args.args[1]
    assert cleared.fields == {} and cleared.version == 2 and cleared.config_id == first.config_id
    overlays.get.return_value = cleared
    assert not (await service.get("builtin", application.owner)).user_configured
    with pytest.raises(ResourceConflictError):
        await service.configure(
            "builtin", application.owner, config={"token": "stale"}, expected_version=1
        )
    overlays.replace.return_value = False
    with pytest.raises(ResourceConflictError):
        await service.reset_configuration("builtin", application.owner)
