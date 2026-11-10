"""Portable JSON values exclude runtime objects and non-finite numbers."""

from pydantic import ConfigDict, JsonValue, TypeAdapter

_JSON = TypeAdapter(JsonValue, config=ConfigDict(allow_inf_nan=False))


def portable_json(value: object) -> JsonValue:
    return _JSON.validate_python(value, strict=True)
