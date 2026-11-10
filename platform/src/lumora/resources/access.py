"""Resource visibility and generic write policy shared by native and retained services."""

from lumora.resources.domain.builtins import BuiltinResourceDescriptor
from lumora.resources.domain.categories import ResourceVisibility
from lumora.resources.domain.models import Resource
from lumora.resources.errors import BuiltInWriteProtectedError, ResourceAccessDeniedError
from lumora.services.identity.scope import CallerScope


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
