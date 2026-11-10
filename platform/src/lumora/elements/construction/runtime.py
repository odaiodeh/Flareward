"""Receiver-local services and runtime capabilities; never serialized with element bundles."""

from collections.abc import Callable
from dataclasses import dataclass, field

from lumora.elements.construction.context import ElementBuildContext
from lumora.programs.graph.runtime_binder import NodeRuntimeBindings


@dataclass(frozen=True)
class ElementRuntime:
    build: ElementBuildContext
    bindings: NodeRuntimeBindings = field(default_factory=NodeRuntimeBindings)
    cancel: Callable[[], None] | None = None
