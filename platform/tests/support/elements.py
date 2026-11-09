"""Deterministic elements obey application contracts and own their resources."""

import asyncio
from typing import Any

from pydantic import BaseModel, ConfigDict

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.factory import BaseFactory
from flareward.elements.node import BaseNode
from flareward.elements.specification import BaseElementSpec
from flareward.programs.graph.models.step_context import StepContext
from flareward.programs.graph.state.graph_state import GraphState
from flareward.programs.graph.state.state_view import StateView
from flareward.programs.graph_elements import GraphElementSpec
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.domain.references import ToolRef
from plugins.routing.elements.router_boolean.spec.spec import (
    RouterBooleanConditionElementSpec,
)
from support.approval import ApprovalSpec
from support.operations import TextSpec
from support.recovery import EffectSpec
from support.secrets import SecretNodeSpec, SecretToolSpec


class DependencyConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    value: str = "hello"
    dependency: ToolRef | None = None
    fail: bool = False


class TextResource:
    def __init__(self, value: str, dependency: Any = None) -> None:
        self.value = value
        self.dependency = dependency
        self.closed = False

    def close(self) -> None:
        self.closed = True


class DependencyFactory(BaseFactory):
    def accepts(self, cfg: DependencyConfig, element_type: str) -> bool:
        return element_type == "platform_dependency"

    def create(self, cfg: DependencyConfig, **dependencies: Any) -> TextResource:
        if cfg.fail:
            raise ValueError("construction failed")
        instance = TextResource(cfg.value, dependencies.get("dependency"))
        return instance


class DependencySpec(BaseElementSpec):
    category = ResourceCategory.TOOL
    type_key = "platform_dependency"
    name = "Test dependency"
    description = "Deterministic resource with transitive dependencies"
    config_schema = DependencyConfig
    factory_cls = DependencyFactory


class EchoConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    dependency: ToolRef
    prefix: str = ""


class EchoNode(BaseNode):
    READS = {"user_prompt"}
    WRITES = {"output"}

    def __init__(self, dependency: TextResource, prefix: str) -> None:
        super().__init__()
        self.dependency = dependency
        self.prefix = prefix
        self.closed = False

    async def run(self, state: StateView) -> StateView:
        state["output"] = self.prefix + self.dependency.value + ":" + state["user_prompt"]
        return state

    def close(self) -> None:
        self.closed = True


class EchoFactory(BaseFactory):
    def accepts(self, cfg: EchoConfig, element_type: str) -> bool:
        return element_type == "platform_echo"

    def create(self, cfg: EchoConfig, **dependencies: Any) -> EchoNode:
        return EchoNode(dependencies["dependency"], cfg.prefix)


class EchoSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_echo"
    name = "Test echo"
    description = "Deterministic node using a dependency"
    config_schema = EchoConfig
    factory_cls = EchoFactory
    reads = EchoNode.total_reads()
    writes = EchoNode.total_writes()


class AsyncEchoNode:
    def __init__(self, dependency: TextResource, prefix: str) -> None:
        self._echo = EchoNode(dependency, prefix)

    def set_context(self, context: StepContext) -> None:
        self._echo.set_context(context)

    async def __call__(self, state: GraphState, config) -> GraphState:
        await asyncio.sleep(0)
        return GraphState.model_validate((await self._echo(state, config)).serialize())


class AsyncEchoFactory(BaseFactory):
    def accepts(self, cfg: EchoConfig, element_type: str) -> bool:
        return element_type == "platform_async_echo"

    def create(self, cfg: EchoConfig, **dependencies: Any) -> AsyncEchoNode:
        return AsyncEchoNode(dependencies["dependency"], cfg.prefix)


class AsyncEchoSpec(GraphElementSpec):
    category = ResourceCategory.NODE
    type_key = "platform_async_echo"
    name = "Async echo"
    description = "Native asynchronous node using existing construction contracts"
    config_schema = EchoConfig
    factory_cls = AsyncEchoFactory
    reads = EchoNode.total_reads()
    writes = EchoNode.total_writes()


ELEMENT_SPECIFICATIONS = (
    DependencySpec,
    EchoSpec,
    AsyncEchoSpec,
    ApprovalSpec,
    EffectSpec,
    SecretToolSpec,
    SecretNodeSpec,
    TextSpec,
)


def element_registry() -> ElementRegistry:
    registry = ElementRegistry()
    for specification in (*ELEMENT_SPECIFICATIONS, RouterBooleanConditionElementSpec):
        registry.register_spec_class(specification)
    return registry
