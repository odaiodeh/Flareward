"""Pure declarative projections shared by publication and execution."""

from pydantic import JsonValue, TypeAdapter

from mas.programs.models import Bindings, LiteralBinding

JSON_VALUE = TypeAdapter(JsonValue)


class BindingError(ValueError):
    """A required value cannot be projected from the supplied data."""


def project(bindings: Bindings, source: JsonValue) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for name, binding in bindings.items():
        if isinstance(binding, LiteralBinding):
            value = binding.value
        else:
            value = source
            try:
                for part in binding.path:
                    if isinstance(value, dict) and isinstance(part, str):
                        value = value[part]
                    elif isinstance(value, list) and isinstance(part, int) and part >= 0:
                        value = value[part]
                    else:
                        raise KeyError(part)
            except (KeyError, IndexError) as error:
                raise BindingError(
                    f"Binding '{name}' cannot resolve path {binding.path}"
                ) from error
        result[name] = JSON_VALUE.validate_json(JSON_VALUE.dump_json(value))
    return result
