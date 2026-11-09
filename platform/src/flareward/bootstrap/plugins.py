"""Load explicitly installed plugin manifests without introducing another behavior registry."""

from collections.abc import Iterable
from importlib import import_module

from flareward.plugins.models import PluginDefinition


def installed_plugins(modules: Iterable[str]) -> tuple[PluginDefinition, ...]:
    plugins: dict[str, PluginDefinition] = {}
    for module in dict.fromkeys(modules):
        plugin = import_module(module).PLUGIN
        if not isinstance(plugin, PluginDefinition):
            raise ValueError("Installed plugin manifest violates its contract")
        previous = plugins.get(plugin.key)
        if previous is not None and previous != plugin:
            raise ValueError("Conflicting installed plugin identity")
        plugins[plugin.key] = plugin
    return tuple(plugins.values())
