"""Incomplete authoring protects supplied secrets and cannot become executable prematurely."""

import pytest
from pydantic import BaseModel, SecretStr, field_validator
from support.application import make_application
from support.draft_configuration import (
    APPLICATION_PROGRAMS,
    ELEMENT_SPECIFICATIONS,
    CredentialConfig,
    DraftProgramConfig,
    complete_configuration,
    definition,
    incomplete_configuration,
    unfinished_bundle,
)
from support.secrets import MemorySecretStore

from lumora.elements.construction.categories import CategoryBuilders
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.instances import ElementInstances
from lumora.programs.service import ProgramContractError
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.domain.construction import ResourceSpec
from lumora.resources.domain.references import ToolRef
from lumora.resources.secrets import is_secret_reference
from lumora.services.identity.domain import Identity


@pytest.fixture
def drafts():
    store = MemorySecretStore()
    application = make_application(store)
    for registration in APPLICATION_PROGRAMS:
        application.applications.register(registration)
    for specification in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    return application, store


async def test_nested_alias_union_mapping_tuple_and_private_metadata_survive_incomplete_save(
    drafts,
):
    application, store = drafts
    root = definition(application.owner, incomplete_configuration())
    saved = await application.programs.save(root, application.owner)
    data = saved.definition.implementation.config
    references = [
        data["providers"]["primary"]["credential"]["token"],
        data["connections"][0]["token"],
        data["pair"][0]["token"],
        data["pair"][1]["token"],
        data["private"]["password"],
    ]
    assert all(is_secret_reference(value) for value in references)
    assert all(
        value not in saved.model_dump_json()
        for value in (
            "provider-private",
            "item-private",
            "pair-private",
            "second-private",
            "settings-private",
        )
    )
    assert "title" not in data and "endpoint" not in data["connections"][0]
    repeated = await application.programs.save(
        saved.definition, application.owner, expected_version=saved.version
    )
    assert repeated.definition == saved.definition and len(store._values) == 5
    assert await application.programs.draft(root.program_id, application.owner) == repeated
    report = await application.programs.validate(
        root.program_id, application.owner, expected_version=repeated.version
    )
    assert not report.valid
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            root.program_id, application.owner, expected_version=repeated.version
        )
    configuration = complete_configuration(data)
    completed = await application.programs.save(
        definition(application.owner, configuration),
        application.owner,
        expected_version=repeated.version,
    )
    published = await application.programs.publish(
        root.program_id, application.owner, expected_version=completed.version
    )
    assert published.definition == completed.definition
    assert len(store._values) == 5
    assert (
        DraftProgramConfig.model_validate(
            completed.definition.implementation.config, by_name=True
        ).title
        == "Completed configuration"
    )


@pytest.mark.parametrize("invalid", ["bound", "extra", "variant", "container"])
async def test_invalid_provided_values_fail_safely_without_persisting_a_draft(drafts, invalid):
    application, _ = drafts
    config = incomplete_configuration()
    if invalid == "bound":
        config["providers"]["primary"]["budget"] = 0
    elif invalid == "extra":
        config["connections"][0]["unexpected"] = "private-invalid-value"
    elif invalid == "variant":
        config["providers"]["primary"]["kind"] = "private-invalid-value"
    else:
        config["connections"] *= 3
    with pytest.raises(ProgramContractError) as raised:
        await application.programs.save(definition(application.owner, config), application.owner)
    assert "private-invalid-value" not in str(raised.value)
    assert not (await application.programs.list(application.owner)).programs


async def test_incomplete_draft_rejects_literal_credentials_without_storage(application):
    secrets = ConfigurationSecrets(application.elements, None)
    with pytest.raises(ValueError, match="secret storage"):
        await secrets.protect_draft(
            DraftProgramConfig, incomplete_configuration(), application.owner
        )


async def test_incomplete_draft_cannot_borrow_another_owners_opaque_secret(drafts):
    application, store = drafts
    saved = await application.programs.save(
        definition(application.owner, incomplete_configuration()), application.owner
    )
    foreign = Identity.user("other")
    with pytest.raises(PermissionError):
        await application.programs.save(
            definition(foreign, saved.definition.implementation.config).model_copy(
                update={"program_id": "foreign"}
            ),
            foreign,
        )
    assert not (await application.programs.list(foreign)).programs
    assert len(store._values) == 5


async def test_unfinished_embedded_resource_is_protected_but_publication_rechecks_construction(
    drafts,
):
    application, store = drafts
    config = complete_configuration(incomplete_configuration())
    config["bundle"] = unfinished_bundle().model_dump(mode="json")
    saved = await application.programs.save(
        definition(application.owner, config), application.owner
    )
    data = saved.definition.implementation.config
    assert "bundle-private" not in saved.model_dump_json()
    assert is_secret_reference(data["bundle"]["entries"][0]["resource"]["config"]["token"])
    with pytest.raises(ProgramContractError):
        await application.programs.publish(
            "configured", application.owner, expected_version=saved.version
        )
    data["bundle"]["entries"][0]["resource"]["config"]["endpoint"] = "bundle"
    # Editing a bundle is authoring: its structural digest must be recomputed.
    data["bundle"].pop("content_digest")
    completed = await application.programs.save(
        definition(application.owner, data), application.owner, expected_version=saved.version
    )
    published = await application.programs.publish(
        "configured", application.owner, expected_version=completed.version
    )
    assert published.definition == completed.definition and len(store._values) == 6


async def test_ambiguous_nonempty_variant_is_refused_before_private_fields_can_be_misclassified(
    application,
):
    class PrivateVariant(BaseModel):
        value: SecretStr
        required: int

    class PublicVariant(BaseModel):
        value: str
        other: int

    class Configuration(BaseModel):
        variant: PrivateVariant | PublicVariant

    secrets = ConfigurationSecrets(application.elements, MemorySecretStore())
    with pytest.raises(ValueError, match="unambiguous"):
        await secrets.protect_draft(
            Configuration, {"variant": {"value": "ambiguous-private"}}, application.owner
        )
    assert await secrets.protect_draft(Configuration, {"variant": {}}, application.owner) == {
        "variant": {}
    }


async def test_supplied_field_validator_is_not_bypassed_when_another_field_is_missing(application):
    class Configuration(BaseModel):
        label: str
        required: str

        @field_validator("label")
        @classmethod
        def approved_label(cls, value: str) -> str:
            if value != "approved":
                raise ValueError("Invalid private label: " + value)
            return value

    secrets = ConfigurationSecrets(application.elements, None)
    with pytest.raises(ValueError) as raised:
        await secrets.protect_draft(Configuration, {"label": "private-label"}, application.owner)
    assert "private-label" not in str(raised.value)


def test_normal_factory_revalidation_accepts_canonical_names_after_alias_normalization(drafts):
    application, _ = drafts
    configuration = CredentialConfig.model_validate(
        {"apiKey": "factory-private", "endpoint": "built"}
    )
    resource = ResourceSpec(
        rid=ToolRef("aliased"), name="Aliased", type="draft_dependency", config=configuration
    )
    registry = ElementInstances()
    builder = CategoryBuilders(application.elements).resource_builders[ResourceCategory.TOOL]
    built = builder.build_resource(resource, registry)
    assert built.value == "built"
