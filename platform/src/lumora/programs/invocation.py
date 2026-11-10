"""Invoke one installed Program implementation through application-owned contracts."""

from typing import Literal

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import BaseModel, JsonValue, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable

from lumora.json_values import portable_json
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import ApplicationRegistration


class ProgramInvocationContractError(ValueError):
    """Safe installed-contract errors without invocation or configuration values."""


class ApplicationInvoker:
    def __init__(self, registration: ApplicationRegistration) -> None:
        self._registration = registration

    async def invoke(
        self, runtime: ProgramRuntime, inputs: JsonValue, configuration: dict[str, JsonValue]
    ) -> JsonValue:
        try:
            config = self._registration.config_schema.model_validate(configuration, by_name=True)
        except ValueError, TypeError:
            raise ProgramInvocationContractError(
                "Program configuration violates its installed contract"
            ) from None
        request = self._data(inputs, self._registration.input_model, "input")
        try:
            result = await self._registration.execute(runtime, request, config)
        except ValidationError:
            raise ProgramInvocationContractError(
                "Program execution violates a model contract"
            ) from None
        return self._data(result, self._registration.result_model, "output")

    @staticmethod
    def _data(
        value: object, model: type[BaseModel] | None, boundary: Literal["input", "output"]
    ) -> JsonValue:
        try:
            portable = portable_json(value)
            if model is not None:
                portable = model.model_validate(portable, by_name=True).model_dump(
                    mode="json", by_alias=False, warnings="error"
                )
                Draft202012Validator(
                    model.model_json_schema(mode="serialization", by_alias=False),
                    registry=Registry(),
                ).validate(portable)
            return portable_json(portable)
        except ValueError, TypeError, SchemaValidationError, Unresolvable, RecursionError:
            raise ProgramInvocationContractError(
                f"Program {boundary} violates its installed contract"
            ) from None
