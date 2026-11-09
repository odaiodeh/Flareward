"""Operation contracts reuse the actual specification, factory and dependency scope."""

import asyncio
from unittest.mock import create_autospec

import pytest
from pydantic import ValidationError
from support.elements import EchoSpec, element_registry
from support.operations import TextInput, TextResult, TextSpec, operation_bundle

from flareward.elements.catalog.service import CatalogService
from flareward.elements.construction.builder import ElementBundleBuilder
from flareward.elements.operation import (
    BaseOperation,
    OperationContext,
    OperationContractError,
    OperationInvoker,
)
from flareward.executions.domain.context import ExecutionContext
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.references import OperationRef
from flareward.services.identity.domain import Identity


@pytest.fixture
def operation_context():
    return OperationContext(
        execution=ExecutionContext(identity=Identity.user("alice"), execution_id="execution"),
        key="typed-work",
    )


async def test_typed_invocation_constructs_transitive_dependencies_and_releases_them(
    operation_context,
):
    registry = element_registry()
    async with ElementBundleBuilder(registry).build(operation_bundle(registry)) as built:
        root = built.element
        middle, leaf = root.dependency, root.dependency.dependency
        assert isinstance(root.dependency.dependency.value, str)
        result = await OperationInvoker(built.specification).invoke(
            root, {"text": "request"}, operation_context
        )
        assert result == {
            "text": "typed:middle:request",
            "execution_id": "execution",
            "key": "typed-work",
        }
        assert not root.closed and not middle.closed and not leaf.closed
    assert root.closed and middle.closed and leaf.closed


async def test_invalid_input_does_not_execute_and_error_does_not_echo_input(operation_context):
    operation = create_autospec(BaseOperation, instance=True)
    with pytest.raises(OperationContractError, match="input") as error:
        await OperationInvoker(TextSpec).invoke(
            operation, {"text": "private", "extra": "secret"}, operation_context
        )
    operation.execute.assert_not_awaited()
    assert "private" not in str(error.value) and "secret" not in str(error.value)


async def test_execution_model_errors_do_not_expose_private_values(operation_context):
    operation = create_autospec(BaseOperation, instance=True)
    with pytest.raises(ValidationError) as invalid:
        TextInput.model_validate({"text": {"token": "private-execution-value"}})
    operation.execute.side_effect = invalid.value
    with pytest.raises(OperationContractError, match="execution") as error:
        await OperationInvoker(TextSpec).invoke(operation, {"text": "valid"}, operation_context)
    assert "private-execution-value" not in str(error.value)


@pytest.mark.parametrize("result", [TextInput(text="private"), {"text": "private"}])
async def test_invalid_result_is_rejected_with_safe_diagnostics(operation_context, result):
    operation = create_autospec(BaseOperation, instance=True)
    operation.execute.return_value = result
    with pytest.raises(OperationContractError) as error:
        await OperationInvoker(TextSpec).invoke(operation, {"text": "input"}, operation_context)
    assert "private" not in str(error.value)


async def test_cancellation_propagates_and_owned_scope_closes(operation_context, monkeypatch):
    entered = asyncio.Event()
    never = asyncio.Event()

    async def wait(request, context):
        entered.set()
        await never.wait()

    registry = element_registry()
    closed = []

    async def invoke():
        async with ElementBundleBuilder(registry).build(operation_bundle(registry)) as built:
            closed.extend(
                [built.element, built.element.dependency, built.element.dependency.dependency]
            )
            monkeypatch.setattr(built.element, "execute", wait)
            await OperationInvoker(built.specification).invoke(
                built.element, {"text": "input"}, operation_context
            )

    task = asyncio.create_task(invoke())
    await asyncio.wait_for(entered.wait(), timeout=5)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert all(resource.closed for resource in closed)


def test_catalog_exposes_operation_input_and_result_contracts():
    detail = CatalogService(element_registry()).get_element_detail("operations", TextSpec.type_key)
    assert detail.input_schema == TextInput.model_json_schema()
    assert detail.output_schema == TextResult.model_json_schema()


def test_operation_reference_and_resource_preference_are_typed():
    assert OperationRef("$ref:work").get_category() == ResourceCategory.OPERATION
    assert ResourceCategory.OPERATION.is_plan_category()


def test_invalid_operation_declarations_fail_during_registration():
    class MissingSchemas(TextSpec):
        input_schema = None

    with pytest.raises(ValueError, match="input and result"):
        element_registry().register_spec_class(MissingSchemas)
    with pytest.raises(OperationContractError):
        OperationInvoker(EchoSpec)


def test_operation_context_requires_an_explicit_key():
    with pytest.raises(ValidationError):
        OperationContext(execution=ExecutionContext(identity=Identity.user("alice")), key="")
