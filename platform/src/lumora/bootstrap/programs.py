"""One application registry with core composition and explicitly installed extensions."""

from collections.abc import Iterable
from importlib import import_module

from lumora.bootstrap.plugins import installed_plugins
from lumora.programs.registry import CoordinatorRegistry

CORE_COORDINATOR_MODULES = ("lumora.programs.composition.programs",)


def installed_coordinators(
    modules: Iterable[str] = (), *, plugins: Iterable[str] = ()
) -> CoordinatorRegistry:
    registry = CoordinatorRegistry()
    contributed = tuple(
        module for plugin in installed_plugins(plugins) for module in plugin.programs
    )
    for name in dict.fromkeys((*CORE_COORDINATOR_MODULES, *contributed, *modules)):
        for registration in import_module(name).COORDINATORS:
            registry.register(registration)
    return registry
