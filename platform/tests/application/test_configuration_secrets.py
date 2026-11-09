"""Configuration credentials are protected through an owner-scoped application port."""

from enum import Enum
from types import SimpleNamespace
from typing import ClassVar
from unittest.mock import create_autospec

import pytest
from pydantic import BaseModel, Field, SecretStr
from support.application import make_application
from support.programs import InvokeConfig
from support.scenarios import resource
from support.secrets import MemorySecretStore, SecretNodeConfig, SecretToolConfig

from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.elements.construction.secrets import ConfigurationSecrets
from flareward.programs.blueprints import (
    BlueprintProgramImporter,
    BlueprintProgramService,
    BlueprintSource,
)
from flareward.programs.domain.models import ApplicationDefinition, ProgramDefinition
from flareward.programs.service import ProgramContractError
from flareward.resources.domain.bundles import BundleEntry, ElementBundle
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.construction import ResourceSpec, StepDef
from flareward.resources.field_encryption import ResourceFieldEncryption
from flareward.resources.secrets import (
    is_secret_reference,
    protected_configuration,
    sensitive_fields,
)
from flareward.services.auth.credentials.ports import TokenCipher
from flareward.services.identity.domain import Identity


def test_read_only_construction_validation_preserves_portable_secret_guard(application):
    original = resource(
        "credential",
        category=ResourceCategory.TOOL,
        type_key="platform_secret_tool",
        config={"api_key": "private-preview-token"},
    )
    resolver = ElementBundleResolver(application.elements)
    assert resolver.validate(original.key, [original]) is None
    with pytest.raises(ValueError, match="Literal credentials must be protected"):
        resolver.resolve(original.key, [original])
    assert original.config == {"api_key": "private-preview-token"}


async def test_literal_secret_is_replaced_and_old_references_remain_owner_scoped(application):
    store = MemorySecretStore()
    secrets = ConfigurationSecrets(application.elements, store)
    original = resource(
        "credential",
        category=ResourceCategory.TOOL,
        type_key="platform_secret_tool",
        config={"api_key": "private-token"},
    )
    protected = await secrets.protect_resource(original, application.owner)
    assert original.config["api_key"] == "private-token"
    assert "private-token" not in protected.model_dump_json()
    assert is_secret_reference(protected.config["api_key"])
    reread = await secrets.protect_resource(protected, application.owner)
    assert reread == protected
    with pytest.raises(PermissionError):
        await secrets.protect_resource(protected, Identity.user("another-owner"))
    resolved = await secrets.resolve(
        SecretToolConfig.model_validate(protected.config), application.owner
    )
    assert resolved["api_key"] == "private-token"


def test_bundle_resolution_refuses_literal_credentials(application):
    literal = resource(
        "credential",
        category=ResourceCategory.TOOL,
        type_key="platform_secret_tool",
        config={"api_key": "private-token"},
    )
    with pytest.raises(ValueError, match="Literal credentials"):
        ElementBundleResolver(application.elements).resolve(literal.key, (literal,))


async def test_secretstr_and_legacy_encrypted_fields_share_protection(application):
    class Nested(BaseModel):
        token: SecretStr

    class Configuration(BaseModel):
        ENCRYPTED_FIELDS: ClassVar[tuple[str, ...]] = ("password",)
        password: str
        children: list[Nested]

    model = Configuration(
        password="password-value", children=[Nested(token=SecretStr("token-value"))]
    )
    secrets = ConfigurationSecrets(application.elements, MemorySecretStore())
    protected = await secrets.protect(model, application.owner)
    assert sensitive_fields(Configuration) == {"password"}
    assert is_secret_reference(protected["children"][0]["token"])
    assert "password-value" not in str(protected) and "token-value" not in str(protected)
    public = Configuration.model_validate(protected)
    assert protected_configuration(public) == protected
    resolved = await secrets.resolve(public, application.owner)
    assert resolved == {"password": "password-value", "children": [{"token": "token-value"}]}


async def test_aliased_secret_fields_and_enum_mapping_keys_round_trip(application):
    class Provider(Enum):
        PRIMARY = "primary"

    class Credential(BaseModel):
        token: SecretStr = Field(alias="apiKey")

    class Configuration(BaseModel):
        providers: dict[Provider, Credential]

    original = Configuration(providers={Provider.PRIMARY: Credential(apiKey="private-value")})
    secrets = ConfigurationSecrets(application.elements, MemorySecretStore())
    protected = await secrets.protect(original, application.owner)
    assert is_secret_reference(protected["providers"]["primary"]["token"])
    portable = Configuration.model_validate(protected, by_name=True)
    assert protected_configuration(portable) == protected
    assert await secrets.resolve(portable, application.owner) == {
        "providers": {"primary": {"token": "private-value"}}
    }


async def test_application_publication_protects_nested_element_bundles():
    application = make_application(MemorySecretStore())
    tool = resource(
        "private",
        category=ResourceCategory.TOOL,
        type_key="platform_secret_tool",
        config={"api_key": "private-value"},
    )
    node = resource(
        "node",
        category=ResourceCategory.NODE,
        type_key="platform_secret_node",
        config={"tool": "$ref:private"},
    )
    bundle = ElementBundle(
        root=node.key,
        entries=(
            BundleEntry(resource=tool),
            BundleEntry(resource=node, dependencies=(tool.key,)),
        ),
    )
    definition = ProgramDefinition(
        program_id="private-application",
        name="Private application",
        owner=application.owner,
        implementation=ApplicationDefinition(
            implementation="invoking",
            version="1",
            config={"bundle": bundle.model_dump(mode="json")},
        ),
    )
    saved = await application.programs.save(definition, application.owner)
    published = await application.programs.publish(
        definition.program_id,
        application.owner,
        expected_version=(
            await application.programs.draft(definition.program_id, application.owner)
        ).version,
    )
    assert "private-value" not in saved.model_dump_json() + published.model_dump_json()
    portable = InvokeConfig.model_validate(saved.definition.implementation.config).bundle
    assert portable.content_digest != bundle.content_digest
    assert (
        ElementBundleResolver(application.elements).resolve(
            portable.root, (entry.resource for entry in portable.entries)
        )
        == portable
    )
    assert is_secret_reference(portable.entries[0].resource.config["api_key"])


async def test_invalid_application_configuration_does_not_echo_private_input(application):
    definition = ProgramDefinition(
        program_id="invalid-application",
        name="Invalid application",
        owner=application.owner,
        implementation=ApplicationDefinition(
            implementation="greeting", version="1", config={"prefix": {"api_key": "private-value"}}
        ),
    )
    with pytest.raises(ProgramContractError) as raised:
        await application.programs.save(definition, application.owner)
    assert "private-value" not in str(raised.value)


def test_existing_resource_encryption_receives_secret_value_instead_of_mask(application):
    class Configuration(BaseModel):
        token: SecretStr

    cipher = create_autospec(TokenCipher, instance=True)
    cipher.encrypt.return_value = "encrypted-value"
    encryption = ResourceFieldEncryption(application.elements, cipher)
    protected = encryption.encrypt_model(Configuration(token=SecretStr("private-value")))
    assert protected == {"token": "encrypted-value"}
    cipher.encrypt.assert_called_once_with("private-value")


async def test_blueprint_import_protects_actual_secretstr_value_instead_of_its_mask():
    class PrivateConfig(BaseModel):
        api_key: SecretStr

    store = MemorySecretStore()
    application = make_application(store)
    source = create_autospec(BlueprintSource, instance=True)
    source.resolve.return_value = SimpleNamespace(
        name="Private blueprint",
        execution_profile=None,
        environments={},
        description="Private typed configuration is protected before saving",
        plan=[StepDef(uid="respond", node="node")],
        nodes=[
            ResourceSpec(
                rid="node",
                name="Node",
                type="platform_secret_node",
                config=SecretNodeConfig(tool="$ref:private"),
            )
        ],
        tools=[
            ResourceSpec(
                rid="private",
                name="Tool",
                type="platform_secret_tool",
                config=PrivateConfig(api_key=SecretStr("private-value")),
            )
        ],
        llms=[],
        providers=[],
        retrievers=[],
        conditions=[],
        sandboxes=[],
        operations=[],
    )
    service = BlueprintProgramService(
        source, BlueprintProgramImporter(application.elements), application.programs
    )
    imported = await service.save("source-blueprint", "imported", application.owner)
    source.resolve.assert_awaited_once_with("source-blueprint", application.owner)
    tool = next(
        resource
        for resource in imported.definition.implementation.resources
        if resource.key.rid == "private"
    )
    assert "private-value" not in imported.model_dump_json()
    assert (
        await store.get(application.owner, tool.config["api_key"])
    ).get_secret_value() == "private-value"
