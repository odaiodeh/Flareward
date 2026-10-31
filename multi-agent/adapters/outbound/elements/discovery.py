"""Discover installed element specs without adopting unrelated loaded subclasses."""

import importlib
import inspect
import logging
import os
import sys
from importlib.resources import files
from pathlib import Path

from mas.application.elements.specification import BaseElementSpec

logger = logging.getLogger(__name__)


class SpecDiscoverer:
    ELEMENTS_MODULE = "mas.elements"
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

    def _import_filesystem_packages(self) -> set[str]:
        if not self._root.exists():
            raise FileNotFoundError(f"Element catalog directory does not exist: {self._root}")
        imported: set[str] = set()
        for category in sorted(self._root.iterdir()):
            if not category.is_dir() or category.name.startswith("__"):
                continue
            for element in sorted(category.iterdir()):
                specification = element / self.SPEC_DIR
                if not (specification / "__init__.py").is_file():
                    continue
                name = f"{self._package}.{category.name}.{element.name}.{self.SPEC_DIR}"
                if self._safe_import(name):
                    imported.add(name)
                if (specification / "spec.py").is_file() and self._safe_import(f"{name}.spec"):
                    imported.add(f"{name}.spec")
        return imported

    @staticmethod
    def _collect_specs(modules: set[str]) -> list[type[BaseElementSpec]]:
        collected: set[type[BaseElementSpec]] = set()
        for name in modules:
            for specification in vars(sys.modules[name]).values():
                if (
                    isinstance(specification, type)
                    and issubclass(specification, BaseElementSpec)
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
            if error.name is None or error.name.split(".")[0] == module_name.split(".")[0]:
                raise
            logger.warning(
                "Element adapter unavailable: %s: %s",
                module_name,
                error,
            )
            return False
        return True
