"""Element packages resolve and construct a complete, owned dependency graph."""

import asyncio
import threading

import pytest
from pydantic import ValidationError
from support.elements import DependencyFactory, element_registry
from support.scenarios import bundle, resource

from lumora.async_work import await_owned
from lumora.elements.construction.builder import ElementBundleBuilder
from lumora.elements.construction.resolver import (
    BundleResolutionError,
    ElementBundleResolver,
)
from lumora.resources.domain.bundles import ElementBundle


@pytest.fixture
def created_resources(monkeypatch):
    created = []
    original = DependencyFactory.create

    def tracked(factory, config, **dependencies):
        instance = original(factory, config, **dependencies)
        created.append(instance)
        return instance

    monkeypatch.setattr(DependencyFactory, "create", tracked)
    return created


def test_transitive_closure_is_topologically_ordered_and_roundtrips():
    resolved = bundle()
    assert [entry.resource.key.rid for entry in resolved.entries] == ["leaf", "middle", "echo"]
    assert ElementBundle.model_validate_json(resolved.model_dump_json()) == resolved


def test_modified_bundle_is_refused():
    data = bundle().model_dump(mode="json")
    data["entries"][0]["resource"]["config"]["value"] = "tampered"
    with pytest.raises(ValidationError, match="digest"):
        ElementBundle.model_validate(data)


def test_missing_resource_has_explicit_identity():
    root = resource("root", config={"dependency": "$ref:missing"})
    with pytest.raises(BundleResolutionError, match="tools/missing"):
        ElementBundleResolver(element_registry()).resolve(root.key, [root])


def test_cycle_reports_dependency_path():
    first = resource("first", config={"dependency": "$ref:second"})
    second = resource("second", config={"dependency": "$ref:first"})
    with pytest.raises(BundleResolutionError, match="tools/first -> tools/second -> tools/first"):
        ElementBundleResolver(element_registry()).resolve(first.key, [first, second])


async def test_construction_reuses_existing_factories_and_closes_resources():
    async with ElementBundleBuilder(element_registry()).build(bundle()) as built:
        root = built.element
        dependency = root.dependency
        leaf = dependency.dependency
        assert dependency.value == "middle"
        assert leaf.value == "hello"
        assert not root.closed
    assert root.closed and dependency.closed and leaf.closed


async def test_partial_construction_failure_releases_earlier_resources(created_resources):
    root = resource("broken", config={"dependency": "$ref:leaf", "fail": True})
    resolved = ElementBundleResolver(element_registry()).resolve(root.key, [root, resource("leaf")])
    with pytest.raises(Exception, match="construction failed"):
        async with ElementBundleBuilder(element_registry()).build(resolved):
            pytest.fail("Construction must fail before yielding")
    assert len(created_resources) == 1
    assert created_resources[0].closed


async def test_parallel_invocations_do_not_share_mutable_resources():
    builder = ElementBundleBuilder(element_registry())
    async with builder.build(bundle()) as first, builder.build(bundle()) as second:
        assert first.element is not second.element
        assert first.element.dependency is not second.element.dependency


def test_registries_are_application_owned():
    first = element_registry()
    second = element_registry()
    assert first is not second


async def test_cancellation_during_factory_creation_drains_before_cleanup(
    monkeypatch, created_resources
):
    entered = threading.Event()
    release = threading.Event()
    original = DependencyFactory.create

    def create(factory, cfg, **dependencies):
        entered.set()
        if not release.wait(timeout=5):
            raise TimeoutError("Test factory was not released")
        return original(factory, cfg, **dependencies)

    monkeypatch.setattr(DependencyFactory, "create", create)

    async def construct():
        root = resource("only")
        resolved = ElementBundleResolver(element_registry()).resolve(root.key, [root])
        async with ElementBundleBuilder(element_registry()).build(resolved):
            pytest.fail("Cancelled construction should never yield")

    task = asyncio.create_task(construct())
    assert await asyncio.to_thread(entered.wait, 5)
    task.cancel()
    await asyncio.sleep(0)
    task.cancel()
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert len(created_resources) == 1
    assert created_resources[0].closed


async def test_owned_async_work_does_not_block_event_loop():
    release = asyncio.Event()
    task = asyncio.create_task(await_owned(release.wait()))
    await asyncio.sleep(0)
    release.set()
    assert await task is True


async def test_owned_cancellation_notifies_the_owner_once_before_draining():
    started, release = asyncio.Event(), asyncio.Event()
    notifications = []

    async def worker():
        started.set()
        await release.wait()

    task = asyncio.create_task(
        await_owned(worker(), on_cancel=lambda: notifications.append("cancelled"))
    )
    await started.wait()
    task.cancel("original cancellation")
    await asyncio.sleep(0)
    task.cancel("later cancellation")
    await asyncio.sleep(0)
    assert notifications == ["cancelled"]
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError, match="original cancellation"):
        await task
