"""Resource visibility and generic write policy shared by native and retained services."""

from mas.core.caller_scope import CallerScope
from mas.core.enums import ResourceVisibility
from mas.resources.builtin_models import BuiltinResourceDescriptor
from mas.resources.errors import BuiltInWriteProtectedError, ResourceAccessDeniedError
from mas.resources.models import Resource


def require_visible(
    resource: Resource, descriptor: BuiltinResourceDescriptor | None, caller: CallerScope
) -> None:
    if caller.is_admin:
        return
    if descriptor is not None:
        if descriptor.visibility != ResourceVisibility.PUBLIC:
            raise KeyError(resource.rid)
    elif caller.identity is not None and not caller.identity.owns(resource.identity):
        raise KeyError(resource.rid)


def require_custom_write(
    resource: Resource, descriptor: BuiltinResourceDescriptor | None, caller: CallerScope
) -> None:
    if caller.is_admin:
        return
    if descriptor is not None:
        raise BuiltInWriteProtectedError()
    if caller.identity is None or not caller.identity.owns(resource.identity):
        raise ResourceAccessDeniedError(resource.rid)
