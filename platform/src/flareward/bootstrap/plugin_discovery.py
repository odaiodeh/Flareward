"""Discover installed element specs without adopting unrelated loaded subclasses."""

import importlib
import inspect
import logging
import os
import sys
from collections.abc import Iterable
from importlib.resources import files
from pathlib import Path

from flareward.elements.specification import BaseElementSpec

logger = logging.getLogger(__name__)


class SpecDiscoverer:
    ELEMENTS_MODULE = "plugins"
    SPEC_DIR = "spec"

    def __init__(
        self,
        elements_root: str | os.PathLike[str] | None = None,
        *,
        package: str = ELEMENTS_MODULE,
    ) -> None:
        self._package = package
        self._root = Path(elements_root) if elements_root is not None else files(package)

    def discover(self) -> list[type[BaseElementSpec]]:
        """Find concrete specs defined by successfully imported catalog packages."""
        return self._collect_specs(self._import_filesystem_packages())

    def discover_modules(self, modules: Iterable[str]) -> list[type[BaseElementSpec]]:
        """Compose an explicit built-in module allowlist with the same optional-dependency rules."""
        return self._collect_specs({name for name in modules if self._safe_import(name)})

    def available_modules(self, modules: Iterable[str]) -> tuple[str, ...]:
        return tuple(name for name in dict.fromkeys(modules) if self._safe_import(name))

    def _import_filesystem_packages(self) -> set[str]:
        if not self._root.exists():
            raise FileNotFoundError(f"Element catalog directory does not exist: {self._root}")
        imported: set[str] = set()
        for initializer in sorted(self._root.rglob("spec/__init__.py")):
            relative = initializer.parent.relative_to(self._root)
            if any(part.startswith("__") for part in relative.parts):
                continue
            name = self._package + "." + ".".join(relative.parts)
            if self._safe_import(name):
                imported.add(name)
            if (initializer.parent / "spec.py").is_file() and self._safe_import(name + ".spec"):
                imported.add(name + ".spec")
        return imported

    @staticmethod
    def _collect_specs(modules: set[str]) -> list[type[BaseElementSpec]]:
        collected: set[type[BaseElementSpec]] = set()
        for name in modules:
            for specification in vars(sys.modules[name]).values():
                if (
                    isinstance(specification, type)
                    and issubclass(specification, BaseElementSpec)
                    and not specification.is_abstract
                    and not inspect.isabstract(specification)
                    and any(
                        specification.__module__ == module
                        or specification.__module__.startswith(f"{module}.")
                        for module in modules
                    )
                ):
                    collected.add(specification)
        # Keep conflicting classes: ElementRegistry rejects duplicate identities explicitly.
        return sorted(
            collected, key=lambda spec: (spec.category.value, spec.type_key, spec.__module__)
        )

    @staticmethod
    def _safe_import(module_name: str) -> bool:
        if module_name in sys.modules:
            return True
        try:
            importlib.import_module(module_name)
        except ModuleNotFoundError as error:
            internal = {
                "flareward",
                "plugins",
                module_name.split(".")[0],
            }
            if error.name is None or error.name.split(".")[0] in internal:
                raise
            logger.warning(
                "Element adapter unavailable: %s: %s",
                module_name,
                error,
            )
            return False
        return True
