"""Async validators keep loop ownership, dependency order, and cancellation cleanup."""

import asyncio

import pytest
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.validation import (
    BaseElementValidator,
    ValidationContext,
    ValidatorReport,
)
from mas.core.element_meta import ElementConfigMeta
from mas.validation.service import ElementValidationService
from support.elements import DependencyConfig, DependencySpec


def metadata(rid, dependency=None):
    return ElementConfigMeta(
        rid=rid,
        category="tools",
        type_key=DependencySpec.type_key,
        name=rid,
        config=DependencyConfig(dependency=dependency),
    )


async def test_async_validation_uses_native_entrypoint_and_preserves_dependency_reports():
    loop = asyncio.get_running_loop()

    class NativeValidator(BaseElementValidator):
        def validate(self, config, context):
            raise AssertionError("Native validation called the synchronous entrypoint")

        async def validate_async(self, config, context):
            assert asyncio.get_running_loop() is loop
            await asyncio.sleep(0)
            checked = {}
            if config.dependency:
                checked[config.dependency.ref] = context.get_dependency_result(
                    config.dependency.ref
                )
                assert checked[config.dependency.ref].is_valid
            return ValidatorReport(checked_dependencies=checked)

    class NativeSpec(DependencySpec):
        validator_cls = NativeValidator

    registry = ElementRegistry()
    registry.register_spec_class(NativeSpec)
    service = ElementValidationService(registry)
    results = await service.validate_ordered_async(
        [metadata("leaf"), metadata("root", "leaf")], ValidationContext()
    )
    assert results["root"].is_valid and results["root"].dependency_results == {
        "leaf": results["leaf"]
    }


async def test_repeated_parent_cancellation_does_not_interrupt_async_validator_cleanup():
    entered, cleanup, release, closed = (asyncio.Event() for _ in range(4))

    class NativeValidator(BaseElementValidator):
        def validate(self, config, context):
            raise AssertionError("Native validation called the synchronous entrypoint")

        async def validate_async(self, config, context):
            entered.set()
            try:
                await asyncio.Future()
            finally:
                cleanup.set()
                await release.wait()
                closed.set()

    class NativeSpec(DependencySpec):
        validator_cls = NativeValidator

    registry = ElementRegistry()
    registry.register_spec_class(NativeSpec)
    task = asyncio.create_task(
        ElementValidationService(registry).validate_async(metadata("root"), ValidationContext())
    )
    try:
        async with asyncio.timeout(2):
            await entered.wait()
            task.cancel()
            await cleanup.wait()
        task.cancel()
        await asyncio.sleep(0)
        assert not task.done() and not closed.is_set()
    finally:
        release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()
