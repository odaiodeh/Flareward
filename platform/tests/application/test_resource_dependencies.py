"""Library dependency inspection rejects incomplete or cyclic authoring data."""

from unittest.mock import create_autospec

import pytest

from flareward.resources.domain.models import Resource
from flareward.resources.registry import ResourcesRegistry
from flareward.resources.resolver import DependencyResolver, ResourceDependencyError


def test_library_dependencies_are_ordered_once_and_missing_resources_are_rejected(application):
    resources = {
        rid: Resource(
            rid=rid,
            identity=application.owner,
            category="tools",
            type="fixture",
            name=rid,
            cfg_dict={},
            nested_refs=dependencies,
        )
        for rid, dependencies in {
            "root": ["left", "right"],
            "left": ["leaf"],
            "right": ["leaf"],
            "leaf": [],
        }.items()
    }
    registry = create_autospec(ResourcesRegistry, instance=True)
    registry.get.side_effect = resources.__getitem__
    resolver = DependencyResolver(registry)
    assert resolver.resolve_all_with_deps(["root", "right"]) == ["leaf", "left", "right", "root"]
    del resources["leaf"]
    with pytest.raises(KeyError):
        resolver.resolve_with_deps("root")
    resources["leaf"] = resources["root"].model_copy(
        update={"rid": "leaf", "nested_refs": ["root"]}
    )
    with pytest.raises(ResourceDependencyError):
        resolver.resolve_with_deps("root")
