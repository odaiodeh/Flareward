"""One application registry with core composition and explicitly installed extensions."""

from collections.abc import Iterable
from importlib import import_module

from lumora.bootstrap.plugins import installed_plugins
from lumora.programs.registry import ApplicationRegistry

CORE_APPLICATION_MODULES = ("lumora.programs.composition.programs",)


def installed_applications(
    modules: Iterable[str] = (), *, plugins: Iterable[str] = ()
) -> ApplicationRegistry:
    registry = ApplicationRegistry()
    contributed = tuple(
        module for plugin in installed_plugins(plugins) for module in plugin.programs
    )
    for name in dict.fromkeys((*CORE_APPLICATION_MODULES, *contributed, *modules)):
        for registration in import_module(name).APPLICATION_PROGRAMS:
            registry.register(registration)
    return registry
