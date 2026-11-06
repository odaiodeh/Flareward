"""Schema-driven resource protection keeps real typed values and nested configuration intact."""

from enum import Enum
from typing import ClassVar
from unittest.mock import create_autospec

import pytest
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.blueprints.repository.repository import BlueprintRepository
from mas.core.enums import ResourceCategory
from mas.core.field_hints import ReadOnlyHint
from mas.resources.authoring import (
    BuiltinConfigurationRepository,
    ResourceAuthoringRepository,
    ResourceAuthoringService,
    ResourceRecord,
)
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.models import ResourceQuery
from mas.resources.registry import ResourcesRegistry
from mas.resources.repository.base import ResourceRepository
from mas.resources.service import CoreResourceService
from pydantic import BaseModel, Field, SecretStr, ValidationError
from support.secrets import MemoryCipher


def test_nested_secretstr_aliases_and_legacy_secret_metadata_round_trip(application):
    class Provider(Enum):
        PRIMARY = "primary"

    class Credential(BaseModel):
        token: SecretStr = Field(alias="apiKey")

    class Configuration(BaseModel):
        ENCRYPTED_FIELDS: ClassVar[tuple[str, ...]] = ("password",)
        password: str
        providers: dict[Provider, Credential]

    cipher = MemoryCipher()
    fields = ResourceFieldEncryption(application.elements, cipher)
    original = Configuration(
        password="private-password",
        providers={Provider.PRIMARY: Credential(apiKey="private-token")},
    )
    encrypted = fields.encrypt_model(original)
    assert "private-password" not in str(encrypted) and "private-token" not in str(encrypted)
    decoded = fields.decrypt(encrypted)
    restored = Configuration.model_validate(decoded, by_name=True)
    assert restored == original
    assert encrypted["providers"]["primary"]["token"] != decoded["providers"]["primary"]["token"]


def test_no_cipher_rejects_private_values_and_keeps_detached_plain_configuration(application):
    class Configuration(BaseModel):
        token: SecretStr

    fields = ResourceFieldEncryption(application.elements, None)
    with pytest.raises(ValueError, match="requires encryption"):
        fields.encrypt_model(Configuration(token="private"))
    source = {"nested": [{"value": "plain"}]}
    copied = fields.decrypt(source)
    copied["nested"][0]["value"] = "changed"
    assert source["nested"][0]["value"] == "plain"


def test_builtin_projection_and_overlay_base_strip_nested_caller_secrets():
    class Credentials(BaseModel):
        token: SecretStr
        endpoint: str

    class Configuration(BaseModel):
        provider: Credentials = Field(json_schema_extra=ReadOnlyHint(read_only=False).to_hints())
        shared: SecretStr

    elements = create_autospec(ElementRegistry, instance=True)
    elements.get_schema.return_value = Configuration
    cipher = MemoryCipher()
    fields = ResourceFieldEncryption(elements, cipher)
    encrypted = fields.encrypt_model(
        Configuration(
            provider=Credentials(
                token="caller-default-private", endpoint="https://provider.invalid"
            ),
            shared="shared-private",
        )
    )
    public = fields.public_config("tools", "fixture", encrypted)
    assert public == {
        "provider": {"token": "", "endpoint": "https://provider.invalid"},
        "shared": "",
    }
    base = fields.strip_unconfigured_secrets("tools", "fixture", encrypted)
    assert base["provider"] == public["provider"]
    assert cipher.decrypt(base["shared"]) == "shared-private"
    assert cipher.decrypt(encrypted["provider"]["token"]) == "caller-default-private"


def test_unsupported_resource_sort_fields_are_rejected(application):
    with pytest.raises(ValidationError, match="sort_by"):
        ResourceQuery(identity=application.owner, sort_by="arbitrary.database.path")


async def test_core_and_native_overlay_writes_preserve_aliased_secretstr(application):
    class Configuration(BaseModel):
        token: SecretStr = Field(
            alias="apiKey", json_schema_extra=ReadOnlyHint(read_only=False).to_hints()
        )

    elements = create_autospec(ElementRegistry, instance=True)
    elements.get_schema.return_value = Configuration
    repository = create_autospec(ResourceRepository, instance=True)
    repository.find_by_name.return_value = None
    cipher = MemoryCipher()
    registry = ResourcesRegistry(
        repository, create_autospec(BlueprintRepository, instance=True), cipher
    )
    fields = ResourceFieldEncryption(elements, cipher)
    core = CoreResourceService(registry, elements, fields)
    resource = core.create(
        identity=application.owner,
        category="tools",
        type="fixture",
        name="Fixture",
        config={"apiKey": "base-private"},
    )
    assert "base-private" not in resource.model_dump_json()
    repository.get.return_value = resource
    assert core.resolve(resource.rid).token.get_secret_value() == "base-private"
    authoring = create_autospec(ResourceAuthoringRepository, instance=True)
    authoring.get.return_value = ResourceRecord(
        resource=resource,
        descriptor=BuiltinResourceDescriptor(rid=resource.rid, visibility="public"),
    )
    overlays = create_autospec(BuiltinConfigurationRepository, instance=True)
    overlays.get.return_value = None
    overlays.replace.return_value = True
    builtin = ResourceAuthoringService(authoring, elements, fields, overlays)
    await builtin.configure(resource.rid, application.owner, config={"apiKey": "caller-private"})
    written = overlays.replace.call_args.args[1]
    assert "caller-private" not in written.model_dump_json()
    assert fields.decrypt(written.fields) == {"token": "caller-private"}
    assert fields.scan_schema_hints(ResourceCategory.TOOL, "fixture") == ({"token"}, {"token"})
