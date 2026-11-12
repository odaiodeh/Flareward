"""Resource capture is schema-directed, owner-scoped and explicit about adoption."""

import pytest
from support.configuration_resources import COORDINATORS
from support.resource_snapshots import MemoryResourceSources
from support.secrets import MemorySecretStore

from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.construction.snapshots import ResourceSnapshotConflict, SavedResourceResolver
from lumora.programs.adapters.memory.program_repository import MemoryProgramRepository
from lumora.programs.authoring import ProgramResourceSelection
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    ProgramBody,
    ProgramDefinition,
)
from lumora.programs.service import ProgramContractError, ProgramService
from lumora.resources.domain.bundles import ElementBundle, ResourceDefinition, ResourceKey
from lumora.services.identity.domain import Identity


@pytest.fixture
def resources(application):
    application.applications.register(COORDINATORS[0])
    source = MemoryResourceSources(application.owner)
    store = MemorySecretStore()
    configuration = ConfigurationSecrets(application.elements, store)
    programs = ProgramService(
        MemoryProgramRepository(),
        application.applications,
        application.elements,
        configuration,
        SavedResourceResolver(source, application.elements, configuration),
    )
    root = ResourceKey(category="operations", rid="work")
    selection = ProgramResourceSelection(
        source=source.reference(root), configuration_path=("stages", 0, "capability")
    )
    definition = ProgramDefinition(
        program_id="configured",
        name="Configured",
        owner=application.owner,
        implementation=CustomCoordinatorDefinition(
            implementation="configured_resource", version="1", config={"stages": [{}]}
        ),
    )
    return programs, source, selection, definition, store


@pytest.mark.parametrize(
    "path,config",
    [
        (("stages", 0, "capability"), {"stages": [{}]}),
        (("stages", 0, "bundle"), {"stages": [{}]}),
        (("stages", 0, "selected", "bundle"), {"stages": [{}]}),
        (("roles", "reviewer", "bundle"), {}),
        (("optional",), {}),
        (("variant", "bundle"), {"variant": {"kind": "operation"}}),
    ],
)
async def test_captures_declared_nested_fields_and_normalizes_aliases(
    application, resources, path, config
):
    programs, source, selection, definition, _ = resources
    definition = definition.model_copy(
        update={"implementation": definition.implementation.model_copy(update={"config": config})}
    )
    saved = await programs.save(
        definition,
        application.owner,
        resource_selections=(selection.model_copy(update={"configuration_path": path}),),
    )
    for stage in saved.definition.implementation.config.get("stages", []):
        assert "capability" not in stage and "selected" not in stage
    revision = await programs.publish(
        definition.program_id, application.owner, expected_version=saved.version
    )
    source.resources.clear()
    assert await programs.revision(revision.reference, application.owner) == revision
    assert "$ref:middle" in revision.model_dump_json()


@pytest.mark.parametrize("field", ["bundle", "capability"])
async def test_changed_closure_requires_replacement_and_preserves_older_revisions(
    application, resources, field
):
    programs, source, selection, definition, _ = resources
    saved = await programs.save(definition, application.owner, resource_selections=(selection,))
    published = await programs.publish(
        definition.program_id, application.owner, expected_version=saved.version
    )
    middle = ResourceKey(category="tools", rid="middle")
    source.resources[middle] = source.resources[middle].model_copy(
        update={"config": {"value": "changed", "dependency": "$ref:leaf"}}
    )
    source.versions[middle] += 1
    canonical = selection.model_copy(update={"configuration_path": ("stages", 0, field)})
    with pytest.raises(ResourceSnapshotConflict):
        await programs.save(
            saved.definition,
            application.owner,
            expected_version=saved.version,
            resource_selections=(canonical,),
        )
    assert (await programs.draft(definition.program_id, application.owner)).version == saved.version
    adopted = await programs.save(
        saved.definition,
        application.owner,
        expected_version=saved.version,
        resource_selections=(canonical.model_copy(update={"adoption": "replace"}),),
    )
    assert "changed" in adopted.model_dump_json() and "changed" not in published.model_dump_json()
    assert await programs.revision(published.reference, application.owner) == published


@pytest.mark.parametrize(
    "path,config",
    [
        (("metadata", "bundle"), {}),
        (("unknown",), {}),
        (("stages", 3, "bundle"), {"stages": [{}]}),
        (("variant", "bundle"), {"variant": {"kind": "empty"}}),
        ((), {}),
    ],
)
async def test_rejects_untyped_unknown_or_unavailable_destinations_without_saving(
    application, resources, path, config
):
    programs, _, selection, definition, _ = resources
    definition = definition.model_copy(
        update={"implementation": definition.implementation.model_copy(update={"config": config})}
    )
    with pytest.raises(ProgramContractError):
        await programs.save(
            definition,
            application.owner,
            resource_selections=(selection.model_copy(update={"configuration_path": path}),),
        )
    with pytest.raises(KeyError):
        await programs.draft(definition.program_id, application.owner)


async def test_nested_owned_body_capture_does_not_modify_sibling_scope(application, resources):
    programs, _, selection, definition, _ = resources
    root = definition.model_copy(
        update={
            "implementation": CustomCoordinatorDefinition(
                implementation="composed",
                version="1",
                children={
                    "greet": ProgramBody(implementation=definition.implementation),
                    "other": ProgramBody(implementation=definition.implementation),
                },
            )
        }
    )
    saved = await programs.save(
        root,
        application.owner,
        resource_selections=(selection.model_copy(update={"body_path": ("greet",)}),),
    )
    assert "bundle" in saved.definition.body_at(("greet",)).implementation.config["stages"][0]
    assert saved.definition.body_at(("other",)).implementation.config["stages"] == [{}]


async def test_stale_and_foreign_sources_are_rejected(application, resources):
    programs, source, selection, definition, _ = resources
    source.versions[selection.source.key] += 1
    with pytest.raises(ResourceSnapshotConflict):
        await programs.save(definition, application.owner, resource_selections=(selection,))
    source.owner = Identity.team(application.owner.id)
    with pytest.raises(KeyError):
        await programs.save(definition, application.owner, resource_selections=(selection,))


async def test_configuration_capture_protects_secret_resources(application, resources):
    programs, source, selection, definition, store = resources
    secret = ResourceDefinition(
        key=ResourceKey(category="tools", rid="private"),
        type_key="platform_secret_tool",
        config={"api_key": "private-capture-value"},
    )
    source.resources[secret.key] = secret
    source.versions[secret.key] = 1
    selected = selection.model_copy(
        update={"source": source.reference(secret.key), "configuration_path": ("optional",)}
    )
    saved = await programs.save(definition, application.owner, resource_selections=(selected,))
    bundle = ElementBundle.model_validate(saved.definition.implementation.config["optional"])
    assert bundle.root == secret.key and len(store._values) == 1
    assert "private-capture-value" not in saved.model_dump_json()


@pytest.mark.parametrize("second_path", [("stages", 0, "capability"), ("stages", 0, "bundle")])
async def test_duplicate_selections_cannot_target_the_same_typed_field(
    application, resources, second_path
):
    programs, _, selection, definition, _ = resources
    with pytest.raises(ProgramContractError, match="only once"):
        await programs.save(
            definition,
            application.owner,
            resource_selections=(
                selection,
                selection.model_copy(update={"configuration_path": second_path}),
            ),
        )
    with pytest.raises(KeyError):
        await programs.draft(definition.program_id, application.owner)


async def test_changing_bundle_root_requires_explicit_replacement(application, resources):
    programs, source, selection, definition, _ = resources
    saved = await programs.save(definition, application.owner, resource_selections=(selection,))
    other = ResourceKey(category="operations", rid="another")
    source.resources[other] = source.resources[selection.source.key].model_copy(
        update={"key": other}
    )
    source.versions[other] = 1
    changed = selection.model_copy(update={"source": source.reference(other)})
    with pytest.raises(ResourceSnapshotConflict, match="replacement"):
        await programs.save(
            saved.definition,
            application.owner,
            expected_version=saved.version,
            resource_selections=(changed,),
        )
    adopted = await programs.save(
        saved.definition,
        application.owner,
        expected_version=saved.version,
        resource_selections=(changed.model_copy(update={"adoption": "replace"}),),
    )
    assert (
        adopted.definition.implementation.config["stages"][0]["bundle"]["root"]["rid"] == other.rid
    )
