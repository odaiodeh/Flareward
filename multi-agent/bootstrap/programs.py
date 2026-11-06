"""One application registry with core composition and explicitly installed extensions."""

from collections.abc import Iterable
from importlib import import_module

from mas.application.programs.registry import ApplicationRegistry

CORE_APPLICATION_MODULES = ("mas.application.programs.composition.programs",)


def installed_applications(modules: Iterable[str] = ()) -> ApplicationRegistry:
    registry = ApplicationRegistry()
    for name in dict.fromkeys((*CORE_APPLICATION_MODULES, *modules)):
        for registration in import_module(name).APPLICATION_PROGRAMS:
            registry.register(registration)
    return registry
