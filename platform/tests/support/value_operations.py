"""Root-value operations use the same specification/factory/invocation conventions."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, RootModel

from lumora.elements.factory import BaseFactory
from lumora.elements.operation import BaseOperation, OperationContext
from lumora.elements.specification import BaseElementSpec
from lumora.executions.domain.preferences import ExecutionSelection
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import GraphDefinition, OperationStep
from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory
from support.typed_programs import Numbers


class ValueConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    multiplier: int = Field(default=2, ge=1)


class ArrayOperation(BaseOperation[Numbers, Numbers]):
    def __init__(self, multiplier: int) -> None:
        self._multiplier = multiplier

    async def execute(self, request: Numbers, context: OperationContext) -> Numbers:
        return Numbers([value * self._multiplier for value in request.root])


class ArrayFactory(BaseFactory[ValueConfig, ArrayOperation]):
    def accepts(self, cfg: ValueConfig, element_type: str) -> bool:
        return element_type == "platform_array_operation"

    def create(self, cfg: ValueConfig, **deps: object) -> ArrayOperation:
        return ArrayOperation(cfg.multiplier)


class ArraySpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "platform_array_operation"
    name = "Array operation"
    description = "RootModel arrays through ordinary operation construction"
    config_schema = ValueConfig
    factory_cls = ArrayFactory
    input_schema = Numbers
    result_schema = Numbers


class TextValue(RootModel[Annotated[str, Field(min_length=1)]]):
    pass


class LengthValue(RootModel[Annotated[int, Field(ge=0)]]):
    pass


class LengthOperation(BaseOperation[TextValue, LengthValue]):
    def __init__(self, multiplier: int) -> None:
        self._multiplier = multiplier

    async def execute(self, request: TextValue, context: OperationContext) -> LengthValue:
        return LengthValue(len(request.root) * self._multiplier)


class LengthFactory(BaseFactory[ValueConfig, LengthOperation]):
    def accepts(self, cfg: ValueConfig, element_type: str) -> bool:
        return element_type == "platform_length_operation"

    def create(self, cfg: ValueConfig, **deps: object) -> LengthOperation:
        return LengthOperation(cfg.multiplier)


class LengthSpec(BaseElementSpec):
    category = ResourceCategory.OPERATION
    type_key = "platform_length_operation"
    name = "Length operation"
    description = "Scalar input/output through ordinary operation construction"
    config_schema = ValueConfig
    factory_cls = LengthFactory
    input_schema = TextValue
    result_schema = LengthValue


ELEMENT_SPECIFICATIONS = (ArraySpec, LengthSpec)


def value_graph(specification: type[BaseElementSpec], profile: str = "thread") -> GraphDefinition:
    resource = ResourceDefinition(
        key=ResourceKey(category=ResourceCategory.OPERATION, rid="work"),
        type_key=specification.type_key,
    )
    return GraphDefinition(
        resources=(resource,),
        steps=(
            OperationStep(
                uid="work",
                element=resource.key,
                execution=ExecutionSelection(profile=profile),
                inputs=PathBinding(path=("input",)),
            ),
        ),
        entry="work",
        exit="work",
        outputs=PathBinding(path=("results", "work")),
    )
