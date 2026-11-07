"""Installed typed operation scenarios; no engine, HTTP, or storage dependencies."""

from typing import Any, Protocol

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.elements.factory import BaseFactory
from mas.application.elements.operation import BaseOperation, OperationContext
from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.core.identity import Identity
from mas.core.ref.models import ToolRef
from mas.domain.element_bundles import ElementBundle, ResourceDefinition, ResourceKey
from mas.domain.execution.context import ExecutionContext
from mas.domain.execution_preferences import ExecutionSelection
from mas.domain.programs.models import GraphDefinition, OperationStep, PathBinding
from pydantic import AliasChoices, AliasPath, BaseModel, ConfigDict, Field


def operation_context(root="root", execution="execution", key="operation") -> OperationContext:
    return OperationContext(
        execution=ExecutionContext(
            root_execution_id=root, execution_id=execution, identity=Identity.user("owner")
        ),
        key=key,
    )


class TextDependency(Protocol):
    value: str


class TextInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1)


class TextResult(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str
    execution_id: str
    key: str


class TextConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dependency: ToolRef
    prefix: str = "typed:"


class TextOperation(BaseOperation[TextInput, TextResult]):
    def __init__(self, dependency: TextDependency, prefix: str) -> None:
        self.dependency = dependency
        self.prefix = prefix
        self.closed = False

    def set_context(self, context: object) -> None:
        """A coincidentally named application API must never receive graph binding."""
        raise AssertionError("Graph context must not be injected into typed operations")

    async def execute(self, request: TextInput, context: OperationContext) -> TextResult:
        return TextResult(
            text=f"{self.prefix}{self.dependency.value}:{request.text}",
            execution_id=context.execution.execution_id,
            key=context.key,
        )

    async def aclose(self) -> None:
        self.closed = True


class TextFactory(BaseFactory):
    def accepts(self, cfg: TextConfig, element_type: str) -> bool:
        return element_type == "platform_text_operation"

    def create(self, cfg: TextConfig, **dependencies: Any) -> TextOperation:
        return TextOperation(dependencies["dependency"], cfg.prefix)


class TextSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "platform_text_operation"
    name = "Typed text operation"
    description = "Typed invocation with a transitively constructed dependency"
    config_schema = TextConfig
    factory_cls = TextFactory
    input_schema = TextInput
    result_schema = TextResult


class AliasedTextInput(TextInput):
    text: str = Field(
        min_length=1, validation_alias=AliasChoices("textAlias", AliasPath("payload", "text"))
    )


class AliasedTextFactory(TextFactory):
    def accepts(self, cfg: TextConfig, element_type: str) -> bool:
        return element_type == "platform_aliased_text_operation"


class AliasedTextSpec(TextSpec):
    type_key = "platform_aliased_text_operation"
    input_schema = AliasedTextInput
    factory_cls = AliasedTextFactory


def operation_resources() -> tuple[ResourceDefinition, ...]:
    return (
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="work"),
            type_key=TextSpec.type_key,
            config={"dependency": "$ref:middle"},
        ),
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.TOOL, rid="middle"),
            type_key="platform_dependency",
            config={"value": "middle", "dependency": "$ref:leaf"},
        ),
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.TOOL, rid="leaf"),
            type_key="platform_dependency",
        ),
    )


def operation_bundle(registry: ElementRegistry) -> ElementBundle:
    return ElementBundleResolver(registry).resolve(
        ResourceKey(category=ResourceCategory.OPERATION, rid="work"), operation_resources()
    )


def operation_graph(profile: str = "thread") -> GraphDefinition:
    return GraphDefinition(
        resources=operation_resources(),
        steps=(
            OperationStep(
                uid="typed-work",
                element=ResourceKey(category=ResourceCategory.OPERATION, rid="work"),
                execution=ExecutionSelection(profile=profile),
                inputs={"text": PathBinding(path=("input", "name"))},
                outputs={"values": PathBinding(path=())},
            ),
        ),
        entry="typed-work",
        exit="typed-work",
        outputs={"answer": PathBinding(path=("values", "text"))},
    )
