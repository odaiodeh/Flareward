"""Validated review configuration and response envelopes at application boundaries."""

import json
from typing import Self

from jsonschema import Draft202012Validator, SchemaError, ValidationError
from mas.core.identity import Identity
from mas.domain.reviews import ReviewDecision, ReviewId, ReviewSpecification, ReviewTemplate
from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012, UnknownDialect


class ReviewSchema:
    """Bounded self-contained JSON Schema; validation performs no remote resolution."""

    @staticmethod
    def validate_schema(schema: dict[str, JsonValue]) -> None:
        try:
            resource: Resource[JsonValue] = Resource.from_contents(
                schema, default_specification=DRAFT202012
            )
            resolver = Registry[JsonValue]().with_resource("", resource).resolver()
            stack: list[tuple[JsonValue, int]] = [(schema, 0)]
            count = 0
            seen: set[int] = set()
            targets: list[dict[str, JsonValue] | bool] = []
            while stack:
                value, depth = stack.pop()
                if id(value) in seen:
                    continue
                seen.add(id(value))
                count += 1
                if count > 1024 or depth > 24:
                    raise ValueError("Review response schema exceeds its complexity limit")
                if isinstance(value, dict):
                    for key, item in value.items():
                        if key == "$id":
                            raise ValueError(
                                "Review schemas do not support nested resource identities"
                            )
                        if (
                            key == "$schema"
                            and item != "https://json-schema.org/draft/2020-12/schema"
                        ):
                            raise ValueError("Review schemas use JSON Schema draft 2020-12")
                        if key in {"$ref", "$dynamicRef"} and (
                            not isinstance(item, str) or not item.startswith("#")
                        ):
                            raise ValueError("Review response schema must be self-contained")
                        if key in {"$ref", "$dynamicRef"}:
                            assert isinstance(item, str)
                            target = resolver.lookup(item).contents
                            if not isinstance(target, dict | bool):
                                raise ValueError("Review reference must identify a schema")
                            targets.append(target)
                            stack.append((target, depth + 1))
                        if key in {"pattern", "patternProperties"}:
                            raise ValueError(
                                "Review schemas do not support regular-expression validation"
                            )
                        if key in {
                            "properties",
                            "$defs",
                            "definitions",
                            "dependentSchemas",
                        } and isinstance(item, dict):
                            stack.extend((child, depth + 1) for child in item.values())
                        elif key in {"allOf", "anyOf", "oneOf", "prefixItems"} and isinstance(
                            item, list
                        ):
                            stack.extend((child, depth + 1) for child in item)
                        elif key in {
                            "items",
                            "additionalProperties",
                            "not",
                            "if",
                            "then",
                            "else",
                            "contains",
                            "propertyNames",
                            "unevaluatedProperties",
                            "unevaluatedItems",
                            "contentSchema",
                        }:
                            stack.append((item, depth + 1))
            Draft202012Validator.check_schema(schema)
            for target in targets:
                Draft202012Validator.check_schema(target)
        except SchemaError, Unresolvable, RecursionError, UnknownDialect:
            raise ValueError("Review response schema is invalid") from None

    @staticmethod
    def validate_response(schema: dict[str, JsonValue], data: JsonValue) -> None:
        try:
            if len(json.dumps(data, ensure_ascii=False, allow_nan=False).encode()) > 65_536:
                raise ValueError("Review response exceeds its byte limit")
            Draft202012Validator(schema, registry=Registry()).validate(data)
        except ValidationError, RecursionError, UnicodeError, Unresolvable:
            raise ValueError("Review response does not match its schema") from None


class ReviewSettings(ReviewSpecification):
    @model_validator(mode="after")
    def valid_schema(self) -> Self:
        ReviewSchema.validate_schema(self.response_schema)
        return self


class ValidatedReviewTemplate(ReviewTemplate):
    @model_validator(mode="after")
    def valid_schema(self) -> Self:
        ReviewSchema.validate_schema(self.response_schema)
        return self


class ReviewPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    owners: tuple[Identity, ...] = Field(min_length=1, max_length=128)
    reviewers: frozenset[str] = Field(min_length=1, max_length=128)
    max_timeout_seconds: int = Field(default=86_400, ge=1, le=2_592_000)


class OpenReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    key: str = Field(min_length=1, max_length=256)
    execution_id: str = Field(min_length=1, max_length=256)
    policy: str = Field(min_length=1, max_length=128)
    specification: ReviewSettings


class SubmitReview(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)
    key: str = Field(min_length=1, max_length=128)
    expected_revision: int = Field(ge=0)
    decision: ReviewDecision
    data: JsonValue = Field(default_factory=dict)


class ReviewHandle(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    review_id: ReviewId


class CloseReview(ReviewHandle):
    expected_revision: int = Field(ge=0)
    superseded_by: ReviewId | None = None
