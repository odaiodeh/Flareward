"""Register installed plugin Elements through the canonical catalog."""

from collections.abc import Iterable
from importlib import import_module

from flareward.bootstrap.plugin_discovery import SpecDiscoverer
from flareward.bootstrap.plugins import installed_plugins
from flareward.bootstrap.settings.plugins import DEFAULT_PLUGINS
from flareward.elements.catalog.element_registry import ElementRegistry


def installed_elements(
    modules: Iterable[str] = (), *, plugins: Iterable[str] = DEFAULT_PLUGINS
) -> ElementRegistry:
    registry = ElementRegistry()
    discovery = SpecDiscoverer()
    contributed = (module for plugin in installed_plugins(plugins) for module in plugin.elements)
    for specification in discovery.discover_modules(contributed):
        registry.register_spec_class(specification)
    for name in modules:
        for specification in import_module(name).ELEMENT_SPECIFICATIONS:
            registry.register_spec_class(specification)
    return registry
