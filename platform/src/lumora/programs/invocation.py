"""Invoke one installed Program implementation through application-owned contracts."""

from typing import Literal

from jsonschema import Draft202012Validator
from jsonschema import ValidationError as SchemaValidationError
from pydantic import BaseModel, JsonValue, ValidationError
from referencing import Registry
from referencing.exceptions import Unresolvable

from lumora.json_values import portable_json
from lumora.programs.domain.interfaces import ProgramInterface
from lumora.programs.ports import ProgramRuntime
from lumora.programs.registry import CoordinatorRegistration, CustomCoordinatorStrategy
from lumora.programs.signatures import ProgramInterfaces


class ProgramInvocationContractError(ValueError):
    """Safe installed-contract errors without invocation or configuration values."""


class CoordinatorInvoker:
    def __init__(self, registration: CoordinatorRegistration, interface: ProgramInterface) -> None:
        if not isinstance(registration.strategy, CustomCoordinatorStrategy):
            raise ProgramInvocationContractError(
                "Custom invocation requires a custom coordinator strategy"
            )
        self._entrypoint = registration.strategy.entrypoint
        try:
            ProgramInterfaces.check_models(registration, interface)
        except ValueError:
            raise ProgramInvocationContractError(
                "Installed coordinator interface differs from the published contract"
            ) from None
        self._registration = registration
        self._interface = interface

    async def invoke(
        self, runtime: ProgramRuntime, inputs: JsonValue, configuration: dict[str, JsonValue]
    ) -> JsonValue:
        try:
            config = self._registration.config_schema.model_validate(configuration, by_name=True)
            ProgramInterfaces.check_registration(self._registration, self._interface, config)
        except ValueError, TypeError:
            raise ProgramInvocationContractError(
                "Program configuration violates its installed contract"
            ) from None
        request = self._data(
            inputs, self._registration.input_model, self._interface.normalized_input_schema, "input"
        )
        try:
            result = await self._entrypoint(runtime, request, config)
        except ValidationError:
            raise ProgramInvocationContractError(
                "Program execution violates a model contract"
            ) from None
        return self._data(
            result,
            self._registration.result_model,
            self._interface.normalized_output_schema,
            "output",
        )

    @staticmethod
    def _data(
        value: object,
        model: type[BaseModel] | None,
        schema: dict[str, JsonValue] | None,
        boundary: Literal["input", "output"],
    ) -> JsonValue:
        try:
            portable = portable_json(value)
            if model is not None:
                portable = model.model_validate(portable, by_name=True).model_dump(
                    mode="json", by_alias=False, warnings="error"
                )
            if schema is not None:
                Draft202012Validator(schema, registry=Registry()).validate(portable)
            return portable_json(portable)
        except ValueError, TypeError, SchemaValidationError, Unresolvable, RecursionError:
            raise ProgramInvocationContractError(
                f"Program {boundary} violates its installed contract"
            ) from None
