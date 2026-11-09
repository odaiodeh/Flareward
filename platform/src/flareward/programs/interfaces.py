"""Bundled JSON interfaces and conservative schema navigation for Program admission."""

from dataclasses import dataclass
from typing import Protocol

from jsonschema import Draft202012Validator, ValidationError
from pydantic import JsonValue
from referencing import Registry, Resource
from referencing.exceptions import Unresolvable
from referencing.jsonschema import DRAFT202012, UnknownDialect

type Schema = bool | dict[str, JsonValue]
type IssuePath = tuple[str | int, ...]


class BindingContractError(ValueError):
    def __init__(self, message: str, path: IssuePath = ()) -> None:
        self.path = path
        super().__init__(message)


@dataclass(frozen=True)
class InterfaceContract:
    document: dict[str, JsonValue]
    schema: Schema = True
    scoped: bool = False

    @staticmethod
    def check_schema(document: dict[str, JsonValue]) -> None:
        Draft202012Validator.check_schema(document)
        try:
            InterfaceContract._dialect(document)
            root = Resource[Schema].from_contents(document, default_specification=DRAFT202012)
            resolver = Registry[Schema]().resolver_with_root(root)
            pending = [(root, resolver)]
            while pending:
                resource, current = pending.pop()
                if isinstance(resource.contents, dict):
                    InterfaceContract._dialect(resource.contents)
                    for keyword in ("$ref", "$dynamicRef"):
                        reference = resource.contents.get(keyword)
                        if isinstance(reference, str):
                            current.lookup(reference)
                pending.extend(
                    (child, current.in_subresource(child)) for child in resource.subresources()
                )
        except UnknownDialect:
            raise BindingContractError("Unsupported interface schema dialect") from None
        except Unresolvable:
            raise BindingContractError(
                "Interface schema references must be bundled with the contract"
            ) from None

    @staticmethod
    def _dialect(schema: dict[str, JsonValue]) -> None:
        declared = schema.get("$schema")
        if declared is not None and (
            not isinstance(declared, str)
            or declared.rstrip("#") != "https://json-schema.org/draft/2020-12/schema"
        ):
            raise BindingContractError("Interface contracts require JSON Schema Draft 2020-12")

    @classmethod
    def root(cls, document: dict[str, JsonValue]) -> InterfaceContract:
        pending = list(
            Resource[Schema]
            .from_contents(document, default_specification=DRAFT202012)
            .subresources()
        )
        while pending:
            resource = pending.pop()
            if resource.id() is not None:
                return cls(document, document, scoped=True)
            pending.extend(resource.subresources())
        return cls(document, document)

    def _with(self, schema: Schema = True) -> InterfaceContract:
        return InterfaceContract(self.document, schema, self.scoped)

    def _resolved(self) -> Schema:
        if self.scoped:
            return True
        schema = self.schema
        seen: set[str] = set()
        while isinstance(schema, dict) and isinstance(schema.get("$ref"), str):
            reference = schema["$ref"]
            assert isinstance(reference, str)
            if reference in seen or not reference.startswith("#/"):
                return True
            seen.add(reference)
            value: JsonValue = self.document
            try:
                for part in reference[2:].split("/"):
                    key = part.replace("~1", "/").replace("~0", "~")
                    value = (
                        value[key]
                        if isinstance(value, dict)
                        else value[int(key)]
                        if isinstance(value, list)
                        else None
                    )
            except KeyError, IndexError, ValueError:
                raise BindingContractError("Interface schema reference is unavailable") from None
            if not isinstance(value, (bool, dict)):
                raise BindingContractError("Interface schema reference is invalid")
            schema = value
        return schema

    def member(
        self, part: str | int, *, depth: int = 64, visited: set[int] | None = None
    ) -> InterfaceContract:
        if depth == 0:
            return self._with()
        schema = self._resolved()
        if not isinstance(schema, dict):
            return self._with(schema)
        visited = set() if visited is None else visited
        if id(schema) in visited:
            return self._with()
        visited.add(id(schema))
        declared = schema.get("type")
        types = (
            {declared}
            if isinstance(declared, str)
            else {item for item in declared if isinstance(item, str)}
            if isinstance(declared, list)
            else set()
        )
        expected = "object" if isinstance(part, str) else "array"
        if types and expected not in types:
            return self._with(False)
        child: Schema = True
        if isinstance(part, str):
            properties = schema.get("properties", {})
            if isinstance(properties, dict) and part in properties:
                value = properties[part]
                if isinstance(value, (bool, dict)):
                    child = value
            elif not schema.get("patternProperties"):
                additional = schema.get("additionalProperties", True)
                if isinstance(additional, (bool, dict)):
                    child = additional
        else:
            maximum = schema.get("maxItems")
            prefix = schema.get("prefixItems", [])
            if isinstance(maximum, int) and part >= maximum:
                child = False
            elif isinstance(prefix, list) and part < len(prefix):
                value = prefix[part]
                if isinstance(value, (bool, dict)):
                    child = value
            else:
                items = schema.get("items", True)
                if isinstance(items, (bool, dict)):
                    child = items
        for keyword in ("anyOf", "oneOf", "allOf"):
            branches = schema.get(keyword)
            if not isinstance(branches, list):
                continue
            projected = [
                self._with(branch).member(part, depth=depth - 1, visited=visited)
                for branch in branches
                if isinstance(branch, (bool, dict))
            ]
            possible = [branch for branch in projected if branch.schema is not False]
            if not possible or (keyword == "allOf" and len(possible) != len(projected)):
                return self._with(False)
            if child is True and (keyword == "allOf" or len(possible) == 1):
                child = possible[0].schema
        return self._with(child)

    def select(self, path: IssuePath) -> InterfaceContract:
        selected = self
        for part in path:
            selected = selected.member(part)
            if selected.schema is False:
                raise BindingContractError("Binding path cannot exist in its source contract")
        return selected

    def required(self, *, depth: int = 64, visited: set[int] | None = None) -> set[str]:
        if depth == 0:
            return set()
        schema = self._resolved()
        if not isinstance(schema, dict):
            return set()
        visited = set() if visited is None else visited
        if id(schema) in visited:
            return set()
        visited.add(id(schema))
        fields = schema.get("required", [])
        result = (
            {name for name in fields if isinstance(name, str)}
            if isinstance(fields, list)
            else set()
        )
        branches = schema.get("allOf", [])
        if isinstance(branches, list):
            for branch in branches:
                if isinstance(branch, (bool, dict)):
                    result.update(self._with(branch).required(depth=depth - 1, visited=visited))
        return result

    def validate_value(self, value: JsonValue) -> None:
        try:
            Draft202012Validator(self.document, registry=Registry()).evolve(
                schema=self.schema
            ).validate(value)
        except ValidationError, Unresolvable, RecursionError:
            raise BindingContractError(
                "Literal binding violates its destination contract"
            ) from None

    def types(
        self, *, depth: int = 64, visited: frozenset[int] = frozenset()
    ) -> frozenset[str] | None:
        schema = self._resolved()
        if schema is False:
            return frozenset()
        if not isinstance(schema, dict) or depth == 0 or id(schema) in visited:
            return None
        visited = visited | {id(schema)}
        declared = schema.get("type")
        known = (
            {declared}
            if isinstance(declared, str)
            else {item for item in declared if isinstance(item, str)}
            if isinstance(declared, list)
            else None
        )
        if known is not None and "number" in known:
            known.add("integer")
        for keyword in ("anyOf", "oneOf", "allOf"):
            branches = schema.get(keyword)
            if not isinstance(branches, list):
                continue
            types = [
                self._with(branch).types(depth=depth - 1, visited=visited)
                for branch in branches
                if isinstance(branch, (bool, dict))
            ]
            if keyword == "allOf":
                for allowed in types:
                    if allowed is not None:
                        known = set(allowed) if known is None else known.intersection(allowed)
            elif types and all(allowed is not None for allowed in types):
                alternatives = set().union(*(allowed for allowed in types if allowed is not None))
                known = alternatives if known is None else known.intersection(alternatives)
        return frozenset(known) if known is not None else None

    def check_overlap(
        self,
        target: InterfaceContract,
        *,
        depth: int = 32,
        visited: frozenset[tuple[int, int]] = frozenset(),
    ) -> None:
        source, destination = self._resolved(), target._resolved()
        pair = (id(source), id(destination))
        if depth == 0 or pair in visited:
            return
        if source is False or destination is False:
            raise BindingContractError("Binding cannot satisfy a closed destination contract")
        source_types, target_types = self.types(), target.types()
        if (
            source_types is not None
            and target_types is not None
            and not source_types & target_types
        ):
            raise BindingContractError(
                "Binding value types cannot satisfy the destination contract"
            )
        for finite in (source, destination):
            if not isinstance(finite, dict):
                continue
            choices = [finite["const"]] if "const" in finite else finite.get("enum")
            if isinstance(choices, list):
                for value in choices:
                    try:
                        self.validate_value(value)
                        target.validate_value(value)
                    except BindingContractError:
                        continue
                    break
                else:
                    raise BindingContractError(
                        "Binding values cannot satisfy the destination contract"
                    )
        if source_types == target_types == frozenset({"object"}):
            for name in self.required() | target.required():
                try:
                    self.member(name).check_overlap(
                        target.member(name), depth=depth - 1, visited=visited | {pair}
                    )
                except BindingContractError as error:
                    raise BindingContractError(str(error), (name, *error.path)) from None


class BindingSource(Protocol):
    def select(self, path: IssuePath) -> InterfaceContract: ...
