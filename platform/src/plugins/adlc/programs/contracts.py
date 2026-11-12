"""ADLC effect validation and required authority capabilities."""

from pydantic import BaseModel, JsonValue, ValidationError

from lumora.resources.domain.bundles import ElementBundle
from lumora.resources.domain.categories import ResourceCategory


def validate_result[T: BaseModel](model: type[T], value: JsonValue) -> T:
    try:
        return model.model_validate(value)
    except ValidationError:
        raise ValueError("Engineering effect violates its contract") from None


def require_service_operation(bundle: ElementBundle, operation: str, service: str) -> None:
    """Require the installed scoped adapter, not an arbitrary lookalike operation."""
    root = next(entry for entry in bundle.entries if entry.resource.key == bundle.root)
    by_key = {entry.resource.key: entry for entry in bundle.entries}
    if (
        root.resource.key.category != ResourceCategory.OPERATION
        or root.resource.type_key != operation
        or len(root.dependencies) != 1
        or by_key[root.dependencies[0]].resource.key.category != ResourceCategory.PROVIDER
        or by_key[root.dependencies[0]].resource.type_key != service
        or len(bundle.entries) != 2
    ):
        raise ValueError("Engineering authority requires the registered scoped service operation")
