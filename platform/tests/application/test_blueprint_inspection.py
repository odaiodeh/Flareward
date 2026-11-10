"""Blueprint inspection authorizes before resolution and uses actual application validators."""

import asyncio
import threading
from unittest.mock import create_autospec

import pytest
from support.elements import DependencyConfig, DependencySpec, EchoConfig, EchoSpec
from support.resolution import resolve_configurations
from support.secrets import MemorySecretStore, SecretToolConfig

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.configuration.meta import ElementConfigMeta
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.exceptions import ElementInspectionError
from lumora.elements.validation import BaseElementValidator, ValidatorReport
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.collector import BlueprintConfigCollector
from lumora.programs.templates.contracts import BlueprintDocument, BlueprintResolutionSource
from lumora.programs.templates.inspection import BlueprintInspectionService
from lumora.services.identity.domain import Identity


@pytest.fixture
def blueprint_case(application):
    authoring = create_autospec(BlueprintAuthoringService, instance=True)
    authoring.get.return_value = BlueprintDocument(
        blueprint_id="stored", identity=application.owner, spec_dict={"plan": []}
    )
    source = create_autospec(BlueprintResolutionSource, instance=True)
    tool = ElementConfigMeta(
        rid="tool",
        category="tools",
        type_key="platform_dependency",
        name="Tool",
        config=DependencyConfig(),
    )
    node = ElementConfigMeta(
        rid="node",
        category="nodes",
        type_key="platform_echo",
        name="Node",
        config=EchoConfig(dependency="tool"),
    )
    source.resolve.return_value = resolve_configurations((node, tool), {})
    store = MemorySecretStore()
    secrets = ConfigurationSecrets(application.elements, store)
    service = BlueprintInspectionService(authoring, source, application.elements, secrets)
    return service, authoring, source, store, secrets


async def test_saved_ownership_precedes_schema_resolution_and_draft_does_not_read_storage(
    application, blueprint_case
):
    service, authoring, source, _, _ = blueprint_case
    authoring.get.side_effect = PermissionError("Access denied")
    with pytest.raises(PermissionError):
        await service.validate(Identity.user("foreign"), blueprint_id="stored")
    source.resolve.assert_not_awaited()
    authoring.get.reset_mock()
    draft = {"plan": []}
    result = await service.validate(application.owner, spec=draft, credential_user_id="human")
    assert result.is_valid and list(result.element_results) == ["tool", "node"]
    source.resolve.assert_awaited_once_with(draft, application.owner, stored=False)
    authoring.get.assert_not_awaited()
    cards = await service.cards(application.owner, spec=draft)
    assert set(cards) == {"node", "tool"}


async def test_inspection_reports_missing_or_wrong_category_and_rejects_cycles(
    application, blueprint_case
):
    service, _, source, _, _ = blueprint_case
    metadata = {
        meta.rid: meta
        for meta in BlueprintConfigCollector().collect(source.resolve.return_value.blueprint)
    }
    node, tool = metadata["node"], metadata["tool"]
    source.resolve.return_value = resolve_configurations((node,), {})
    result = await service.validate(application.owner, spec={"plan": []})
    assert not result.is_valid and not result.element_results["tool"].is_valid
    with pytest.raises(KeyError):
        await service.cards(application.owner, spec={"plan": []})
    wrong = tool.model_copy(
        update={
            "rid": "tool",
            "category": node.category,
            "type_key": node.type_key,
            "config": EchoConfig(dependency="absent"),
        }
    )
    source.resolve.return_value = resolve_configurations((node, wrong), {})
    result = await service.validate(application.owner, spec={"plan": []})
    assert (
        not result.is_valid
        and "category mismatch" in result.element_results["node"].messages[0].message
    )
    source.resolve.return_value = resolve_configurations(
        (tool.model_copy(update={"config": DependencyConfig(dependency="tool")}),), {}
    )
    with pytest.raises(ValueError, match="cycle"):
        await service.validate(application.owner, spec={"plan": []})
    source.resolve.return_value = resolve_configurations((tool, tool), {})
    with pytest.raises(ValueError, match="Duplicate"):
        await service.cards(application.owner, spec={"plan": []})


async def test_local_inspection_hydrates_references_and_accepts_unsaved_literals_without_put(
    application, blueprint_case
):
    service, _, source, _, secrets = blueprint_case
    reference = await secrets.protect(SecretToolConfig(api_key="private-token"), application.owner)
    meta = ElementConfigMeta(
        rid="secret",
        category="tools",
        type_key="platform_secret_tool",
        name="Secret",
        config=SecretToolConfig.model_validate(reference),
    )
    source.resolve.return_value = resolve_configurations((meta,), {})
    result = await service.validate(application.owner, spec={"plan": []})
    assert result.is_valid and "private-token" not in result.model_dump_json()
    with pytest.raises(PermissionError):
        await service.cards(Identity.user("foreign"), spec={"plan": []})
    source.resolve.return_value = resolve_configurations(
        (meta.model_copy(update={"config": SecretToolConfig(api_key="literal-private")}),), {}
    )
    assert (await service.validate(application.owner, spec={"plan": []})).is_valid
    with pytest.raises(ValueError, match="Literal"):
        await secrets.resolve(SecretToolConfig(api_key="literal-private"), application.owner)


async def test_authored_secret_resolution_never_writes_and_preserves_runtime_literal_rejection(
    application,
):
    store = create_autospec(MemorySecretStore, instance=True)
    secrets = ConfigurationSecrets(application.elements, store)
    assert await secrets.resolve_authored(
        SecretToolConfig(api_key="private"), application.owner
    ) == {"api_key": "private", "fail": False, "fail_on_run": False}
    store.put.assert_not_awaited()
    store.get.assert_not_awaited()


async def test_cards_use_typed_dependencies_instead_of_stale_metadata(application, blueprint_case):
    _, authoring, source, _, _ = blueprint_case

    class LeafSpec(DependencySpec):
        capability_names = ["Leaf"]

    elements = ElementRegistry()
    elements.register_spec_class(LeafSpec)
    elements.register_spec_class(EchoSpec)
    service = BlueprintInspectionService(
        authoring, source, elements, ConfigurationSecrets(elements, None)
    )
    cards = await service.cards(application.owner, spec={"plan": []})
    assert [capability.name for capability in cards["node"].capabilities] == ["Leaf"]


@pytest.mark.parametrize("cancel", [False, True])
async def test_blueprint_probes_drain_cancellation_and_sanitize_provider_failures(
    application, blueprint_case, cancel
):
    _, authoring, source, _, _ = blueprint_case
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()
    loop_thread = threading.get_ident()

    class BlockingValidator(BaseElementValidator):
        def validate(self, config, context):
            assert threading.get_ident() != loop_thread
            assert context.user_id == application.owner.id and context.credential_user_id == "human"
            entered.set()
            assert release.wait(5)
            finished.set()
            if not cancel:
                raise RuntimeError("private-provider-failure")
            return ValidatorReport()

    class ProbeSpec(DependencySpec):
        validator_cls = BlockingValidator

    elements = ElementRegistry()
    elements.register_spec_class(ProbeSpec)
    source.resolve.return_value = resolve_configurations(
        (
            next(
                meta
                for meta in BlueprintConfigCollector().collect(
                    source.resolve.return_value.blueprint
                )
                if meta.rid == "tool"
            ),
        ),
        {},
    )
    service = BlueprintInspectionService(
        authoring, source, elements, ConfigurationSecrets(elements, None)
    )
    task = asyncio.create_task(
        service.validate(application.owner, spec={"plan": []}, credential_user_id="human")
    )
    try:
        assert await asyncio.to_thread(entered.wait, 5)
        if cancel:
            task.cancel()
        await asyncio.sleep(0)
        assert not task.done()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError if cancel else ElementInspectionError) as raised:
        await task
    assert "private-provider-failure" not in str(raised.value)
    assert finished.is_set()
