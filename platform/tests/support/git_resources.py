"""Normal Git provider/operation definitions shared by Program scenarios."""

from lumora.resources.domain.bundles import ResourceDefinition, ResourceKey
from lumora.resources.domain.categories import ResourceCategory


def git_resources(repository="product"):
    return (
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.PROVIDER, rid="repository"),
            type_key="git_repository",
            config={"repository": repository},
        ),
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="resolve"),
            type_key="resolve_git_revision",
            config={"source": "$ref:repository"},
        ),
        ResourceDefinition(
            key=ResourceKey(category=ResourceCategory.OPERATION, rid="read"),
            type_key="read_git_file",
            config={"source": "$ref:repository"},
        ),
    )
