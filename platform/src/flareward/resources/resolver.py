"""Resolve stored authoring dependencies without accepting missing resources or cycles."""

from flareward.resources.registry import ResourcesRegistry


class ResourceDependencyError(ValueError):
    def __init__(self) -> None:
        super().__init__("Resource dependency cycle")


class DependencyResolver:
    def __init__(self, resource_registry: ResourcesRegistry) -> None:
        self._registry = resource_registry

    def resolve_with_deps(self, rid: str) -> list[str]:
        return self.resolve_all_with_deps([rid])

    def resolve_all_with_deps(self, rids: list[str]) -> list[str]:
        complete: set[str] = set()
        active: set[str] = set()
        ordered: list[str] = []

        def visit(rid: str) -> None:
            if rid in active:
                raise ResourceDependencyError()
            if rid in complete:
                return
            resource = self._registry.get(rid)
            active.add(rid)
            for dependency in resource.nested_refs:
                visit(dependency)
            active.remove(rid)
            complete.add(rid)
            ordered.append(rid)

        for rid in rids:
            visit(rid)
        return ordered
