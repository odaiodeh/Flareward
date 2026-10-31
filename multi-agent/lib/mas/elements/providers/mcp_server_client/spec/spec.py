from typing import ClassVar

from mas.application.elements.specification import BaseElementSpec
from mas.core.enums import ResourceCategory
from mas.elements.providers.mcp_server_client.card_builder import McpProviderCardBuilder
from mas.elements.providers.mcp_server_client.config import McpProviderConfig
from mas.elements.providers.mcp_server_client.identifiers import META, Identifier
from mas.elements.providers.mcp_server_client.mcp_provider_factory import McpProviderFactory
from mas.elements.providers.mcp_server_client.validator import McpProviderValidator


class McpProviderElementSpec(BaseElementSpec):
    """
    Element specification for MCP Provider.

    Provides MCP server connection and management capabilities.
    Note: Actions for MCP operations are now managed independently via the ActionsService.
    """

    category: ClassVar[ResourceCategory] = ResourceCategory.PROVIDER
    type_key = Identifier.TYPE
    name = META.name
    description = META.description
    config_schema = McpProviderConfig
    factory_cls = McpProviderFactory
    tags = META.tags
    validator_cls = McpProviderValidator
    card_builder_cls = McpProviderCardBuilder
