"""Optional capability installation exposes schemas through the existing catalog."""

from mas.application.elements.catalog.service import CatalogService
from mas.core.enums import ResourceCategory
from mas_plugins.git.specification import CheckoutGitSpec, GitRepositorySpec, ResolveGitSpec

from bootstrap.elements import installed_elements


def test_git_plugin_installs_without_a_second_registry_or_constructing_a_connection():
    registry = installed_elements(("mas_plugins.git.specification",))
    catalog = CatalogService(registry)
    assert registry.get_spec(ResourceCategory.PROVIDER, "git_repository") is GitRepositorySpec
    for specification in (ResolveGitSpec, CheckoutGitSpec):
        detail = catalog.get_element_detail("operations", specification.type_key)
        assert detail.input_schema == specification.input_schema.model_json_schema()
        assert detail.output_schema == specification.result_schema.model_json_schema()
    connection = catalog.get_element_detail("providers", "git_repository")
    assert set(connection.config_schema["properties"]) == {"repository"}
