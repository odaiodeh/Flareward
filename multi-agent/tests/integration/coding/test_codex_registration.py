"""The real node spec participates in the existing catalog and protected configuration path."""

import pytest
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.application.elements.node import BaseNode
from mas.core.element_deps import ElementBuildContext
from mas.core.enums import ResourceCategory
from mas.core.execution_context import ExecutionContextHolder
from mas.core.identity import Identity
from mas.core.secrets import is_secret_reference
from mas.elements.nodes.codex_agent.codex_agent_node import CodexAgentNode
from mas.elements.nodes.codex_agent.config import CodexAgentNodeConfig
from mas.elements.nodes.codex_agent.identifiers import Identifier
from mas.elements.nodes.codex_agent.spec.spec import CodexAgentNodeElementSpec
from pydantic import SecretStr
from support.secrets import MemorySecretStore


async def test_catalog_configuration_and_factory_preserve_the_node_contract():
    registry = ElementRegistry()
    registry.register_spec_class(CodexAgentNodeElementSpec)
    specification = registry.get_spec(ResourceCategory.NODE, Identifier.TYPE)
    configuration = CodexAgentNodeConfig(model="explicit-test", api_key=SecretStr("private-test"))
    secrets = ConfigurationSecrets(registry, MemorySecretStore())
    owner = Identity.user("owner")
    protected = await secrets.protect(configuration, owner)
    assert "private-test" not in str(protected)
    assert is_secret_reference(protected["api_key"])
    resolved = await secrets.resolve(CodexAgentNodeConfig.model_validate(protected), owner)
    assert resolved["api_key"] == "private-test"
    with pytest.raises(PermissionError):
        await secrets.resolve(
            CodexAgentNodeConfig.model_validate(protected), Identity.user("other")
        )
    factory = specification.factory_cls()
    assert factory.accepts(configuration, Identifier.TYPE)
    node = factory.create(
        configuration, deps=ElementBuildContext(execution_ctx=ExecutionContextHolder())
    )
    assert isinstance(node, CodexAgentNode) and isinstance(node, BaseNode)
