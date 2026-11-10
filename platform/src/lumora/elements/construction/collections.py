"""Structural input shared by full blueprints and targeted resource construction."""

from collections.abc import Iterable
from typing import Protocol

from lumora.resources.domain.construction import ResourceSpec


class ResourceCollections(Protocol):
    providers: Iterable[ResourceSpec]
    llms: Iterable[ResourceSpec]
    retrievers: Iterable[ResourceSpec]
    tools: Iterable[ResourceSpec]
    sandboxes: Iterable[ResourceSpec]
    nodes: Iterable[ResourceSpec]
    conditions: Iterable[ResourceSpec]
    operations: Iterable[ResourceSpec]
