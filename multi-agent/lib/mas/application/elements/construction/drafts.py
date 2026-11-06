"""Schema-bearing authoring values; incomplete data never pretends to be a runtime model."""

from dataclasses import dataclass
from dataclasses import field as dataclass_field
from types import UnionType
from typing import Annotated, Any, Self, TypeAliasType, Union, get_args, get_origin

from pydantic import AliasChoices, AliasPath, BaseModel, TypeAdapter, ValidationError
from pydantic.fields import FieldInfo
from pydantic_core import PydanticUndefined, to_jsonable_python

from mas.core.secrets import serialized_key


@dataclass(frozen=True)
class ConfigurationDraft:
    schema: type[BaseModel]
    values: dict[str, object] = dataclass_field(repr=False)

    @classmethod
    def parse(cls, schema: type[BaseModel], data: object) -> BaseModel | Self:
        try:
            return schema.model_validate(data, by_name=True)
        except ValidationError as error:
            errors = error.errors(include_input=False, include_context=False)
            if not any(item["type"] in ("missing", "union_tag_not_found") for item in errors):
                raise ValueError("Invalid configuration") from None
        if not isinstance(data, dict) or schema.__pydantic_root_model__:
            raise ValueError("Incomplete configuration requires an object model")
        values: dict[str, object] = {}
        consumed: set[str] = set()
        for name, field in schema.model_fields.items():
            paths = cls._paths(
                name, field, by_alias=schema.model_config.get("validate_by_alias", True)
            )
            locations = {(name,), *(tuple(path.path) for path in paths)}
            if any(
                tuple(item["loc"]) in locations
                and item["type"] not in ("missing", "union_tag_not_found")
                for item in errors
            ):
                raise ValueError("Invalid configuration field")
            for path in paths:
                raw = path.search_dict_for_path(data)
                if raw is not PydanticUndefined:
                    values[name] = cls._value(field.rebuild_annotation(), raw)
                    consumed.add(str(path.path[0]))
                    break
        extra = data.keys() - consumed
        if extra and schema.model_config.get("extra") == "forbid":
            raise ValueError("Unexpected configuration fields")
        if schema.model_config.get("extra") == "allow":
            if extra & values.keys():
                raise ValueError("Conflicting configuration aliases")
            values.update({key: data[key] for key in extra})
        return cls(schema, values)

    @staticmethod
    def _paths(name: str, field: FieldInfo, *, by_alias: bool) -> list[AliasPath]:
        alias = field.validation_alias if by_alias else None
        choices = alias.choices if isinstance(alias, AliasChoices) else [alias]
        return [
            item if isinstance(item, AliasPath) else AliasPath(item)
            for item in choices
            if item is not None
        ] + [AliasPath(name)]

    @classmethod
    def _value(cls, annotation: Any, raw: object) -> object:
        try:
            return TypeAdapter(annotation).validate_python(raw, by_name=True)
        except ValidationError as error:
            errors = error.errors(include_input=False, include_context=False)
            if not any(item["type"] in ("missing", "union_tag_not_found") for item in errors):
                raise ValueError("Invalid configuration value") from None
            outer_error = any(not item["loc"] for item in errors)
        while isinstance(annotation, TypeAliasType) or get_origin(annotation) is Annotated:
            annotation = (
                annotation.__value__
                if isinstance(annotation, TypeAliasType)
                else get_args(annotation)[0]
            )
        origin, args = get_origin(annotation), get_args(annotation)
        if origin in (Union, UnionType):
            candidates: list[object] = []
            for branch in args:
                try:
                    candidates.append(cls._value(branch, raw))
                except ValueError:
                    continue
            if len(candidates) == 1:
                return candidates[0]
            if raw == {} and candidates:
                return {}
            raise ValueError("Choose an unambiguous configuration variant")
        if outer_error:
            raise ValueError("Invalid configuration value")
        if isinstance(annotation, type) and issubclass(annotation, BaseModel):
            return cls.parse(annotation, raw)
        if origin is list and isinstance(raw, list):
            return [cls._value(args[0], item) for item in raw]
        if origin is tuple and isinstance(raw, (list, tuple)):
            types = (args[0],) * len(raw) if len(args) == 2 and args[1] is Ellipsis else args
            if len(types) != len(raw):
                raise ValueError("Invalid configuration tuple")
            return tuple(cls._value(kind, item) for kind, item in zip(types, raw, strict=True))
        if origin is dict and isinstance(raw, dict):
            return {
                cls._value(args[0], key): cls._value(args[1], item) for key, item in raw.items()
            }
        raise ValueError("Invalid configuration value")

    @classmethod
    def serialize(cls, value: object) -> Any:
        if isinstance(value, cls):
            return {name: cls.serialize(item) for name, item in value.values.items()}
        if isinstance(value, BaseModel):
            return value.model_dump(mode="json")
        if isinstance(value, dict):
            return {serialized_key(key): cls.serialize(item) for key, item in value.items()}
        if isinstance(value, (list, tuple)):
            return [cls.serialize(item) for item in value]
        return to_jsonable_python(value)
