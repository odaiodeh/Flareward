"""Compose installed plugin discovery into an otherwise pure application catalog."""

from collections.abc import Iterable
from importlib import import_module

from mas.application.elements.catalog.element_registry import ElementRegistry
from outbound.elements.discovery import SpecDiscoverer


def installed_elements(modules: Iterable[str] = ()) -> ElementRegistry:
    registry = ElementRegistry()
    for specification in SpecDiscoverer().discover():
        registry.register_spec_class(specification)
    for name in modules:
        for specification in import_module(name).ELEMENT_SPECIFICATIONS:
            registry.register_spec_class(specification)
    return registry
