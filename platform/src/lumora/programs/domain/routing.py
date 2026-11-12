"""Validate complete routing selections without exposing selected values."""

from collections.abc import Mapping


class RouteSelectionError(ValueError):
    """A condition returned an invalid or undeclared routing outcome."""


def normalize_route_selection(value: object, branches: Mapping[str, str]) -> str | list[str]:
    result: str | list[str]
    if isinstance(value, bool):
        result = str(value).lower()
    elif isinstance(value, str):
        result = value
    elif isinstance(value, (list, tuple)) and all(isinstance(item, str) for item in value):
        result = list(value)
    else:
        raise RouteSelectionError("Route must select a boolean, string or sequence of strings")
    labels = [result] if isinstance(result, str) else result
    if any(label not in branches for label in labels):
        raise RouteSelectionError("Route selected an undeclared branch")
    return result
