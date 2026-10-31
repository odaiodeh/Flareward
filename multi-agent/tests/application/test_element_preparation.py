"""Async preparation belongs to the same scope that constructs and releases dependencies."""

import asyncio

import pytest
from mas.application.elements.construction.builder import ElementBundleBuilder
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.application.elements.exceptions import PluginConfigurationError
from mas.core.element_deps import ElementBuildContext
from mas.core.execution_context import ExecutionContext, ExecutionContextHolder
from support.application import make_application
from support.elements import DependencyFactory, TextResource, element_registry
from support.scenarios import resource
from support.secrets import MemorySecretStore, SecretToolFactory


@pytest.fixture
async def preparation_case(monkeypatch):
    events = []
    started, release = asyncio.Event(), asyncio.Event()
    loop = asyncio.get_running_loop()

    class PreparedResource(TextResource):
        async def prepare_element(self):
            assert asyncio.get_running_loop() is loop
            events.append("prepare:" + self.value)
            if self.value == "blocked":
                started.set()
                try:
                    await release.wait()
                finally:
                    events.append("drained:" + self.value)
            if self.value == "fail":
                raise PluginConfigurationError("preparation failed", {})

        def close(self):
            events.append("close:" + self.value)
            super().close()

    def create(factory, cfg, **dependencies):
        if dependencies.get("dependency") is not None:
            assert "prepare:leaf" in events
        return PreparedResource(cfg.value, dependencies.get("dependency"))

    monkeypatch.setattr(DependencyFactory, "create", create)
    return events, started, release


async def test_dependencies_finish_preparation_before_dependents_are_constructed(preparation_case):
    events, _, _ = preparation_case
    registry = element_registry()
    root = resource("root", config={"value": "root", "dependency": "$ref:leaf"})
    bundle = ElementBundleResolver(registry).resolve(
        root.key, [root, resource("leaf", config={"value": "leaf"})]
    )
    async with ElementBundleBuilder(registry).build(bundle):
        assert events == ["prepare:leaf", "prepare:root"]
    assert events[-2:] == ["close:root", "close:leaf"]


async def test_failed_preparation_releases_the_resource_that_failed(preparation_case):
    events, _, _ = preparation_case
    registry = element_registry()
    root = resource("root", config={"value": "fail"})
    bundle = ElementBundleResolver(registry).resolve(root.key, [root])
    with pytest.raises(PluginConfigurationError, match="preparation failed"):
        async with ElementBundleBuilder(registry).build(bundle):
            pytest.fail("Preparation must fail before yielding")
    assert events == ["prepare:fail", "close:fail"]


async def test_cancelled_preparation_drains_before_resource_cleanup(preparation_case):
    events, started, _ = preparation_case
    registry = element_registry()
    root = resource("root", config={"value": "blocked"})
    bundle = ElementBundleResolver(registry).resolve(root.key, [root])

    async def build():
        async with ElementBundleBuilder(registry).build(bundle):
            pytest.fail("Cancelled preparation must not yield")

    task = asyncio.create_task(build())
    await asyncio.wait_for(started.wait(), timeout=2)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert events == ["prepare:blocked", "drained:blocked", "close:blocked"]


async def test_private_preparation_errors_are_masked_and_the_resource_is_closed(monkeypatch):
    store = MemorySecretStore()
    application = make_application(store)
    source = resource(
        "private",
        type_key="platform_secret_tool",
        config={"api_key": "private-prepare-value"},
    )
    protected = await ConfigurationSecrets(application.elements, store).protect_resource(
        source,
        application.owner,
    )
    bundle = ElementBundleResolver(application.elements).resolve(protected.key, [protected])
    holder = ExecutionContextHolder()
    holder.context = ExecutionContext(identity=application.owner)
    original = SecretToolFactory.create
    closed = []

    def create(factory, config, **dependencies):
        instance = original(factory, config, **dependencies)

        async def prepare():
            raise ValueError("SDK error exposes " + config.api_key)

        instance.prepare_element = prepare
        instance.close = lambda: closed.append(True)
        return instance

    monkeypatch.setattr(SecretToolFactory, "create", create)
    with pytest.raises(ValueError, match="Element construction failed") as error:
        async with ElementBundleBuilder(application.elements).build(
            bundle,
            ElementBuildContext(execution_ctx=holder, configuration_secrets=store),
        ):
            pytest.fail("Private preparation must fail before yielding")
    assert closed == [True]
    assert "private-prepare-value" not in str(error.value)
    assert error.value.__suppress_context__
