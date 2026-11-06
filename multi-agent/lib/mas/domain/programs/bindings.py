"""Pure declarative projections shared by publication and execution."""

from typing import overload

from pydantic import JsonValue, ValidationError

from mas.domain.json_values import portable_json
from mas.domain.programs.models import Binding, Bindings, LiteralBinding, Projection


class BindingError(ValueError):
    """A required value cannot be projected from the supplied data."""


@overload
def project(bindings: Bindings, source: JsonValue) -> dict[str, JsonValue]: ...


@overload
def project(bindings: Projection, source: JsonValue) -> JsonValue: ...


def project(bindings: Projection, source: JsonValue) -> JsonValue:
    if isinstance(bindings, dict):
        return {name: _value(binding, source) for name, binding in bindings.items()}
    return _value(bindings, source)


def _value(binding: Binding, source: JsonValue) -> JsonValue:
    value = binding.value if isinstance(binding, LiteralBinding) else source
    try:
        if not isinstance(binding, LiteralBinding):
            for part in binding.path:
                if isinstance(value, dict) and isinstance(part, str):
                    value = value[part]
                elif isinstance(value, list) and isinstance(part, int) and part >= 0:
                    value = value[part]
                else:
                    raise KeyError(part)
        return portable_json(value)
    except KeyError, IndexError, ValidationError:
        raise BindingError("Binding cannot resolve a portable value") from None
