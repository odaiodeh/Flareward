"""Shared secret-field metadata and opaque configuration references, without storage SDKs."""

from collections.abc import Callable, Iterator
from typing import Any, Protocol, get_args
from uuid import UUID

from pydantic import BaseModel, SecretStr
from pydantic_core import to_jsonable_python

from lumora.services.identity.domain import Identity

SECRET_PREFIX = "lumora-secret:v1:"


class ConfigurationSecretStore(Protocol):
    async def put(self, owner: Identity, value: SecretStr) -> str: ...
    async def get(self, owner: Identity, reference: str) -> SecretStr: ...


def sensitive_fields(schema: type[BaseModel]) -> set[str]:
    fields = set(getattr(schema, "ENCRYPTED_FIELDS", ()))
    for name, field in schema.model_fields.items():
        extra = field.json_schema_extra
        hints = extra.get("hints", {}) if isinstance(extra, dict) else {}
        if "secret" in hints or SecretStr in (field.annotation, *get_args(field.annotation)):
            fields.add(name)
    return fields


def reference_id(value: str) -> str:
    if not value.startswith(SECRET_PREFIX):
        raise ValueError("Expected an opaque configuration secret reference")
    try:
        return UUID(hex=value[len(SECRET_PREFIX) :]).hex
    except ValueError:
        raise ValueError("Invalid configuration secret reference") from None


def is_secret_reference(value: Any) -> bool:
    if not isinstance(value, str) or not value.startswith(SECRET_PREFIX):
        return False
    reference_id(value)
    return True


def secret_text(value: Any) -> str | None:
    if isinstance(value, SecretStr):
        return value.get_secret_value()
    if value is None or isinstance(value, str):
        return value
    raise ValueError("Secret configuration fields must contain strings or references")


def public_default(value: str | None, default: Any) -> bool:
    # Empty credentials and public schema defaults (such as EMPTY for a mock)
    # contain no private value. SecretStr defaults remain protected.
    return value in (None, "") or (not isinstance(default, SecretStr) and value == default)


def serialized_key(key: Any) -> str:
    """Use Pydantic's JSON mapping-key rules, including enums and non-string keys."""
    return next(iter(to_jsonable_python({key: None})))


def protected_configuration(model: BaseModel) -> Any:
    """Preserve reference serialization while refusing literal private field values."""
    return _configuration(model, protected=True)


def authored_configuration(model: BaseModel) -> Any:
    """Extract private values for protection; this intermediate value is never portable."""
    return _configuration(model, protected=False)


def map_configuration_secrets(
    model: BaseModel, transform: Callable[[str | None, Any], str | None]
) -> Any:
    """Transform declared secrets without losing typed nested fields or SecretStr values."""
    return _configuration(model, protected=False, transform=transform)


def redact_configuration_values(configuration: BaseModel, payload: Any) -> Any:
    """Remove declared private field values from diagnostic content without changing model types."""
    private: set[str] = set()

    def collect(value: str | None, default: Any) -> str | None:
        if value and not public_default(value, default):
            private.add(value)
        return value

    map_configuration_secrets(configuration, collect)
    if not private:
        return payload
    values = sorted(private, key=len, reverse=True)

    def redact(value: Any) -> Any:
        if type(value) is str:
            for secret in values:
                value = value.replace(secret, "[redacted]")
            return value
        if isinstance(value, BaseModel):
            fields = {name: getattr(value, name) for name in type(value).model_fields}
            return value.model_copy(
                update={
                    name: redact(item)
                    for name, item in {**fields, **(value.model_extra or {})}.items()
                }
            )
        if isinstance(value, dict):
            return {key: redact(item) for key, item in value.items()}
        if isinstance(value, list):
            return [redact(item) for item in value]
        if isinstance(value, tuple):
            return tuple(redact(item) for item in value)
        return value

    return redact(payload)


def _configuration(
    model: BaseModel,
    *,
    protected: bool,
    transform: Callable[[str | None, Any], str | None] | None = None,
) -> Any:
    data = model.model_dump(mode="json")
    if not isinstance(data, dict):
        return data
    sensitive = sensitive_fields(type(model))
    for name, field in type(model).model_fields.items():
        if name not in data:
            continue
        value = getattr(model, name)
        if name in sensitive:
            raw = secret_text(value)
            if (
                protected
                and not public_default(raw, field.default)
                and not is_secret_reference(raw)
            ):
                raise ValueError(
                    "Literal credentials must be protected before constructing a bundle"
                )
            data[name] = transform(raw, field.default) if transform else raw
        else:
            data[name] = _configuration_value(
                value, data[name], protected=protected, transform=transform
            )
    return data


def configuration_secret_references(value: Any) -> Iterator[str]:
    if isinstance(value, BaseModel):
        sensitive = sensitive_fields(type(value))
        for name in type(value).model_fields:
            item = getattr(value, name)
            if name in sensitive:
                raw = secret_text(item)
                if is_secret_reference(raw):
                    yield raw
            else:
                yield from configuration_secret_references(item)
    elif isinstance(value, dict):
        for item in value.values():
            yield from configuration_secret_references(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from configuration_secret_references(item)


def _configuration_value(
    value: Any,
    serialized: Any,
    *,
    protected: bool,
    transform: Callable[[str | None, Any], str | None] | None,
) -> Any:
    if isinstance(value, BaseModel):
        return _configuration(value, protected=protected, transform=transform)
    if isinstance(value, (list, tuple)):
        return [
            _configuration_value(item, encoded, protected=protected, transform=transform)
            for item, encoded in zip(value, serialized, strict=True)
        ]
    if isinstance(value, dict):
        return {
            serialized_key(key): _configuration_value(
                item, serialized[serialized_key(key)], protected=protected, transform=transform
            )
            for key, item in value.items()
        }
    return serialized
