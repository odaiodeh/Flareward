"""The real coding operation uses the shared catalog, factory and protected configuration."""

import pytest
from pydantic import SecretStr
from support.secrets import MemorySecretStore

from lumora.bootstrap.elements import installed_elements
from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.coding.operation import CodingOperation
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.operation import BaseOperation
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.secrets import is_secret_reference
from lumora.services.identity.domain import Identity
from plugins.codex.config import CodexConfig
from plugins.codex.identifiers import TYPE_KEY
from plugins.codex.specification import CodexSpec


async def test_catalog_configuration_and_factory_use_the_operation_contract():
    registry = ElementRegistry()
    registry.register_spec_class(CodexSpec)
    specification = registry.get_spec(ResourceCategory.OPERATION, TYPE_KEY)
    configuration = CodexConfig(model="explicit-test", api_key=SecretStr("private-test"))
    secrets = ConfigurationSecrets(registry, MemorySecretStore())
    owner = Identity.user("owner")
    protected = await secrets.protect(configuration, owner)
    assert "private-test" not in str(protected)
    assert is_secret_reference(protected["api_key"])
    resolved = await secrets.resolve(CodexConfig.model_validate(protected), owner)
    assert resolved["api_key"] == "private-test"
    with pytest.raises(PermissionError):
        await secrets.resolve(CodexConfig.model_validate(protected), Identity.user("other"))
    factory = specification.factory_cls()
    assert factory.accepts(configuration, TYPE_KEY)
    operation = factory.create(configuration)
    assert isinstance(operation, CodingOperation) and isinstance(operation, BaseOperation)


def test_explicit_coding_module_uses_normal_plugin_registration():
    registry = installed_elements(
        (
            "plugins.codex.specification",
            "plugins.artifacts.elements.specification",
        )
    )
    assert registry.get_spec(ResourceCategory.OPERATION, TYPE_KEY) is CodexSpec
    assert (
        registry.get_spec(ResourceCategory.PROVIDER, "artifact_workspace").type_key
        == "artifact_workspace"
    )
