"""Typed operation behavior and invocation, independent of graph state or engines."""

from abc import ABC, abstractmethod

from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError

from flareward.elements.specification import BaseElementSpec
from flareward.executions.domain.context import ExecutionContext
from flareward.json_values import portable_json
from flareward.resources.domain.categories import ResourceCategory


class OperationContext(BaseModel):
    """Receiver-supplied invocation metadata, without graph state or engine SDK objects."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    execution: ExecutionContext
    key: str = Field(min_length=1)


class BaseOperation[Input: BaseModel, Output: BaseModel](ABC):
    @abstractmethod
    async def execute(self, request: Input, context: OperationContext) -> Output: ...


class OperationContractError(ValueError):
    """Safe diagnostics: invalid values must not appear in contract errors."""


class OperationInvoker:
    """Validate one registered operation's request and portable result."""

    def __init__(self, specification: type[BaseElementSpec]) -> None:
        if (
            specification.category != ResourceCategory.OPERATION
            or specification.input_schema is None
            or specification.result_schema is None
        ):
            raise OperationContractError("Operation requires input and result model schemas")
        self._input = specification.input_schema
        self._output = specification.result_schema

    async def invoke(
        self,
        operation: BaseOperation[BaseModel, BaseModel],
        inputs: JsonValue,
        context: OperationContext,
    ) -> JsonValue:
        try:
            request = self._input.model_validate(portable_json(inputs), by_name=True)
        except ValidationError:
            raise OperationContractError("Operation input violates its contract") from None
        try:
            result = await operation.execute(request, context)
        except ValidationError:
            raise OperationContractError("Operation execution violates a model contract") from None
        if not isinstance(result, BaseModel):
            raise OperationContractError("Operation must return a model result")
        try:
            validated = self._output.model_validate(result.model_dump(), by_name=True)
            return portable_json(validated.model_dump(mode="json", warnings="error"))
        except ValueError, TypeError:
            raise OperationContractError("Operation output violates its contract") from None
