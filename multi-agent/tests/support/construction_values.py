"""Portable dependency graphs shared by domain and application construction tests."""

from mas.domain.element_bundles import ResourceDefinition, ResourceKey


def dependency_chain(length: int) -> tuple[ResourceDefinition, ...]:
    return tuple(
        ResourceDefinition(
            key=ResourceKey(category="tools", rid=f"dependency-{index}"),
            type_key="platform_dependency",
            config={"dependency": f"$ref:dependency-{index + 1}"} if index + 1 < length else {},
        )
        for index in range(length)
    )
