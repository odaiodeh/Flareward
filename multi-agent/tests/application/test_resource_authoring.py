"""Resource use cases validate schemas and enforce policy through application-owned ports."""

from unittest.mock import create_autospec

import pytest
from mas.core.enums import ResourceCategory
from mas.core.execution_preferences import ResourceExecutionDefaults
from mas.core.identity import Identity
from mas.resources.authoring import (
    ResourceAuthoringRepository,
    ResourceAuthoringService,
    ResourceRecord,
)
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.errors import (
    BuiltInWriteProtectedError,
    ResourceAccessDeniedError,
    ResourceConflictError,
    ResourceInUseError,
)
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.models import Resource
from support.secrets import MemoryCipher


@pytest.fixture
def resource_case(application):
    repository = create_autospec(ResourceAuthoringRepository, instance=True)
    cipher = MemoryCipher()
    resource = Resource(
        rid="tool",
        identity=application.owner,
        category="tools",
        type="platform_secret_tool",
        name="Private tool",
        cfg_dict={"api_key": cipher.encrypt("private-value")},
    )
    repository.get.return_value = ResourceRecord(resource=resource)
    repository.replace.return_value = repository.delete.return_value = True
    repository.usage.return_value = ([], [])
    service = ResourceAuthoringService(
        repository, application.elements, ResourceFieldEncryption(application.elements, cipher)
    )
    return service, repository, cipher


async def test_create_encrypts_declared_secrets_and_collects_typed_dependencies(
    application, resource_case
):
    service, repository, cipher = resource_case
    created = await service.create(
        application.owner,
        category=ResourceCategory.TOOL,
        type_key="platform_secret_tool",
        name="Secret",
        config={"api_key": "private-value"},
    )
    assert "private-value" not in created.model_dump_json()
    assert cipher.decrypt(created.cfg_dict["api_key"]) == "private-value"
    repository.create.assert_awaited_once()
    dependent = await service.create(
        application.owner,
        category=ResourceCategory.TOOL,
        type_key="platform_dependency",
        name="Dependent",
        config={"dependency": "$ref:catalog-tool"},
    )
    assert dependent.nested_refs == ["catalog-tool"]


async def test_update_round_trips_encrypted_configuration_and_fences_stale_writes(
    application, resource_case
):
    service, repository, cipher = resource_case
    previous = repository.get.return_value.resource.model_copy(deep=True)
    updated = await service.update(
        "tool", application.owner, config=previous.cfg_dict, expected_version=1
    )
    assert updated.version == 2 and cipher.decrypt(updated.cfg_dict["api_key"]) == "private-value"
    assert repository.get.return_value.resource == previous
    repository.replace.assert_awaited_once()
    repository.replace.reset_mock()
    with pytest.raises(ResourceConflictError):
        await service.update("tool", application.owner, config={}, expected_version=0)
    repository.replace.assert_not_awaited()
    repository.replace.return_value = False
    with pytest.raises(ResourceConflictError):
        await service.update("tool", application.owner, config={"api_key": "new"})


async def test_ownership_and_builtin_write_guards_run_before_configuration_parsing(
    application, resource_case
):
    service, repository, _ = resource_case
    with pytest.raises(KeyError):
        await service.get("tool", Identity.user("other"))
    with pytest.raises(ResourceAccessDeniedError):
        await service.update("tool", Identity.user("other"), config={"invalid": True})
    repository.get.return_value.descriptor = BuiltinResourceDescriptor(
        rid="tool", visibility="public"
    )
    assert (await service.get("tool", Identity.user("other"))).ownership == "builtin"
    assert (await service.get("tool", Identity.user("other"))).cfg_dict["api_key"] == ""
    with pytest.raises(BuiltInWriteProtectedError):
        await service.delete("tool", application.owner)
    repository.get.return_value.descriptor.visibility = "draft"
    with pytest.raises(KeyError):
        await service.get("tool", application.owner)
    repository.replace.assert_not_awaited()
    repository.delete.assert_not_awaited()


async def test_delete_preserves_referenced_resources_and_fences_concurrent_changes(
    application, resource_case
):
    service, repository, _ = resource_case
    repository.usage.return_value = (["blueprint"], ["dependent"])
    with pytest.raises(ResourceInUseError):
        await service.delete("tool", application.owner)
    repository.delete.assert_not_awaited()
    repository.usage.return_value = ([], [])
    repository.delete.return_value = False
    with pytest.raises(ResourceConflictError):
        await service.delete("tool", application.owner)


async def test_invalid_configuration_errors_do_not_echo_private_values(application, resource_case):
    service, repository, _ = resource_case
    with pytest.raises(ValueError) as raised:
        await service.create(
            application.owner,
            category=ResourceCategory.TOOL,
            type_key="platform_secret_tool",
            name="Invalid",
            config={"api_key": {"value": "private-value"}},
        )
    assert "private-value" not in str(raised.value)
    repository.create.assert_not_awaited()


async def test_resource_execution_defaults_are_separate_preserved_and_explicitly_clearable(
    application, resource_case
):
    service, repository, _ = resource_case
    created = await service.create(
        application.owner,
        category=ResourceCategory.NODE,
        type_key="platform_echo",
        name="Agent",
        config={"dependency": "$ref:tool"},
        execution=ResourceExecutionDefaults(profile="isolated-agent"),
    )
    assert created.execution.profile == "isolated-agent"
    assert created.cfg_dict == {"dependency": "$ref:tool", "prefix": ""}
    repository.get.return_value = ResourceRecord(resource=repository.create.call_args.args[0])
    preserved = await service.update(created.rid, application.owner, config=created.cfg_dict)
    assert preserved.execution == created.execution
    changed = await service.update(
        created.rid,
        application.owner,
        config=created.cfg_dict,
        execution=ResourceExecutionDefaults(profile="another-profile"),
    )
    assert changed.execution.profile == "another-profile"
    cleared = await service.update(
        created.rid,
        application.owner,
        config=created.cfg_dict,
        execution=ResourceExecutionDefaults(),
    )
    assert cleared.execution.profile is None
    assert repository.get.return_value.resource.execution.profile == "isolated-agent"


async def test_construction_dependencies_cannot_select_an_invocation_backend(
    application, resource_case
):
    service, repository, _ = resource_case
    with pytest.raises(ValueError, match="only to nodes and conditions"):
        await service.create(
            application.owner,
            category=ResourceCategory.TOOL,
            type_key="platform_dependency",
            name="Dependency",
            config={},
            execution=ResourceExecutionDefaults(profile="process"),
        )
    with pytest.raises(ValueError, match="only to nodes and conditions"):
        await service.update(
            "tool",
            application.owner,
            config={"api_key": "private-value"},
            execution=ResourceExecutionDefaults(profile="process"),
        )
    repository.create.assert_not_awaited()
    repository.replace.assert_not_awaited()
