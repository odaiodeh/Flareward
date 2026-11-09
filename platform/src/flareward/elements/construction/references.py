"""Discover and resolve typed references without interpreting arbitrary strings."""

from collections.abc import Iterator
from typing import Any

from pydantic import BaseModel

from flareward.resources.domain.bundles import ResourceKey
from flareward.resources.domain.references import Ref


def references(value: Any) -> Iterator[ResourceKey]:
    if isinstance(value, Ref):
        yield ResourceKey(category=value.get_category(), rid=value.ref)
    elif isinstance(value, BaseModel):
        for name in type(value).model_fields:
            yield from references(getattr(value, name))
    elif isinstance(value, dict):
        for item in value.values():
            yield from references(item)
    elif isinstance(value, (list, tuple)):
        for item in value:
            yield from references(item)


def resolve_reference_value(value: Any, registry: Any) -> Any:
    if isinstance(value, Ref):
        return registry.get_instance(value.get_category(), value.ref)
    if isinstance(value, list):
        return [resolve_reference_value(item, registry) for item in value]
    if isinstance(value, tuple):
        return tuple(resolve_reference_value(item, registry) for item in value)
    if isinstance(value, dict):
        return {key: resolve_reference_value(item, registry) for key, item in value.items()}
    if isinstance(value, BaseModel):
        return {
            name: resolve_reference_value(getattr(value, name), registry)
            for name in type(value).model_fields
        }
    return value
