"""Optional capability installation exposes schemas through the existing catalog."""

from lumora.bootstrap.elements import installed_elements
from lumora.elements.catalog.service import CatalogService
from lumora.resources.domain.categories import ResourceCategory
from plugins.git.elements.specification import (
    CheckoutGitSpec,
    GitRepositorySpec,
    ReadGitSpec,
    ResolveGitSpec,
)


def test_git_plugin_installs_without_a_second_registry_or_constructing_a_connection():
    registry = installed_elements(("plugins.git.elements.specification",))
    catalog = CatalogService(registry)
    assert registry.get_spec(ResourceCategory.PROVIDER, "git_repository") is GitRepositorySpec
    for specification in (ResolveGitSpec, CheckoutGitSpec, ReadGitSpec):
        detail = catalog.get_element_detail("operations", specification.type_key)
        assert detail.input_schema == specification.input_schema.model_json_schema()
        assert detail.output_schema == specification.result_schema.model_json_schema()
    connection = catalog.get_element_detail("providers", "git_repository")
    assert set(connection.config_schema["properties"]) == {"repository"}
