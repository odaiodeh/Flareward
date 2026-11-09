"""Installed configuration scenarios shared by application and real execution tests."""

from copy import deepcopy
from enum import StrEnum
from typing import Annotated, ClassVar, Literal

from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field, JsonValue, SecretStr

from flareward.elements.factory import BaseFactory
from flareward.elements.specification import BaseElementSpec
from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    ProgramDefinition,
)
from flareward.programs.ports import ProgramRuntime
from flareward.programs.registry import ApplicationRegistration
from flareward.resources.domain.bundles import (
    BundleEntry,
    ElementBundle,
    ResourceDefinition,
    ResourceKey,
)
from flareward.resources.domain.categories import ResourceCategory
from flareward.services.identity.domain import Identity
from support.operations import operation_graph

__runengine_contract__ = "flareward-test-draft-configuration-v1"


class CredentialConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    token: SecretStr = Field(validation_alias=AliasChoices("apiKey", AliasPath("auth", "key")))
    endpoint: str = Field(min_length=1)


class RemoteConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["remote"]
    credential: CredentialConfig
    budget: int = Field(ge=1)


class LocalConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["local"]
    directory: str


class Provider(StrEnum):
    PRIMARY = "primary"
    SECONDARY = "secondary"


class PrivateSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ENCRYPTED_FIELDS: ClassVar[tuple[str, ...]] = ("password",)
    password: str
    destination: str


class DraftProgramConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str
    providers: dict[Provider, Annotated[RemoteConfig | LocalConfig, Field(discriminator="kind")]]
    connections: list[CredentialConfig] = Field(min_length=1, max_length=2)
    pair: tuple[CredentialConfig, CredentialConfig] | None = None
    private: PrivateSettings
    bundle: ElementBundle | None = None


class DraftDependency:
    def __init__(self, endpoint: str):
        self.value = endpoint


class DraftDependencyFactory(BaseFactory[CredentialConfig, DraftDependency]):
    def accepts(self, cfg: CredentialConfig, element_type: str) -> bool:
        return element_type == "draft_dependency"

    def create(self, cfg: CredentialConfig, **dependencies: object) -> DraftDependency:
        return DraftDependency(cfg.endpoint)


class DraftDependencySpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = "draft_dependency"
    name = "Draft dependency"
    description = "A required credential and endpoint exercise safe unfinished construction"
    config_schema = CredentialConfig
    factory_cls = DraftDependencyFactory


async def configured_program(
    runtime: ProgramRuntime, inputs: JsonValue, config: BaseModel
) -> JsonValue:
    assert isinstance(config, DraftProgramConfig)
    return {"title": config.title, "endpoint": config.connections[0].endpoint}


APPLICATION_PROGRAMS = (
    ApplicationRegistration("draft_configured", "1", DraftProgramConfig, configured_program),
)
ELEMENT_SPECIFICATIONS = (DraftDependencySpec,)


def incomplete_configuration() -> dict[str, JsonValue]:
    return {
        "providers": {
            "primary": {"kind": "remote", "budget": 1, "credential": {"apiKey": "provider-private"}}
        },
        "connections": [{"auth": {"key": "item-private"}}],
        "pair": [{"apiKey": "pair-private"}, {"apiKey": "second-private", "endpoint": "second"}],
        "private": {"password": "settings-private"},
    }


def complete_configuration(config: dict[str, JsonValue]) -> dict[str, JsonValue]:
    value = deepcopy(config)
    value["title"] = "Completed configuration"
    providers, connections, pair, private = (
        value["providers"],
        value["connections"],
        value["pair"],
        value["private"],
    )
    assert isinstance(providers, dict) and isinstance(connections, list)
    assert isinstance(pair, list) and isinstance(private, dict)
    primary = providers["primary"]
    assert isinstance(primary, dict)
    provider_credential = primary["credential"]
    assert isinstance(provider_credential, dict)
    provider_credential["endpoint"] = "provider"
    for credential in connections:
        assert isinstance(credential, dict)
        credential["endpoint"] = "connection"
    first = pair[0]
    assert isinstance(first, dict)
    first["endpoint"] = "first"
    private["destination"] = "destination"
    return value


def definition(owner: Identity, config: dict[str, JsonValue]) -> ProgramDefinition:
    return ProgramDefinition(
        program_id="configured",
        name="Configured",
        owner=owner,
        implementation=ApplicationDefinition(
            implementation="draft_configured", version="1", config=config
        ),
    )


def unfinished_bundle() -> ElementBundle:
    resource = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.TOOL, rid="private"),
        type_key="draft_dependency",
        config={"apiKey": "bundle-private"},
    )
    return ElementBundle(root=resource.key, entries=(BundleEntry(resource=resource),))


def unfinished_resource_graph(profile: str = "thread") -> GraphDefinition:
    graph = operation_graph(profile)
    resource = unfinished_bundle().entries[0].resource
    operation = graph.resources[0].model_copy(update={"config": {"dependency": "$ref:private"}})
    return graph.model_copy(update={"resources": (operation, resource)})
