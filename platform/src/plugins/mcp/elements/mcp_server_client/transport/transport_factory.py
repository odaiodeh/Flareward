"""
Factory for creating MCP transport managers.

Provides a clean, extensible mechanism for instantiating the correct
transport manager based on the requested protocol type.
"""

import logging
from typing import Dict, Optional, Type

from plugins.mcp.elements.mcp_server_client.transport.base_transport import (
    BaseTransportManager,
)
from plugins.mcp.elements.mcp_server_client.transport.enums import McpTransportType
from plugins.mcp.elements.mcp_server_client.transport.sse_transport import (
    SseTransportManager,
)
from plugins.mcp.elements.mcp_server_client.transport.streamable_http_transport import (
    StreamableHttpTransportManager,
)

logger = logging.getLogger(__name__)


class TransportFactory:
    """
    Factory for creating protocol-specific MCP transport managers.

    Maintains a registry of transport type → manager class mappings.
    Supports both built-in transports and runtime registration of
    custom implementations.

    Usage:
        factory = TransportFactory()
        transport = factory.create(
            transport_type=McpTransportType.SSE,
            endpoint="http://host:8004/sse",
        )
    """

    _DEFAULT_REGISTRY: Dict[McpTransportType, Type[BaseTransportManager]] = {
        McpTransportType.SSE: SseTransportManager,
        McpTransportType.STREAMABLE_HTTP: StreamableHttpTransportManager,
    }

    def __init__(self):
        """Initialize with a copy of the default transport registry."""
        self._registry: Dict[McpTransportType, Type[BaseTransportManager]] = dict(
            self._DEFAULT_REGISTRY
        )

    def register(
        self,
        transport_type: McpTransportType,
        manager_cls: Type[BaseTransportManager],
    ) -> None:
        """
        Register a custom transport manager class.

        Allows extending the factory with new transport protocols
        at runtime without modifying existing code.

        Args:
            transport_type: The transport type enum value to register
            manager_cls: The BaseTransportManager subclass to associate

        Raises:
            TypeError: If manager_cls is not a BaseTransportManager subclass
        """
        if not (isinstance(manager_cls, type) and issubclass(manager_cls, BaseTransportManager)):
            raise TypeError(
                f"manager_cls must be a subclass of BaseTransportManager, got {manager_cls!r}"
            )
        self._registry[transport_type] = manager_cls
        logger.debug("Registered transport %s → %s", transport_type.value, manager_cls.__name__)

    def create(
        self,
        transport_type: McpTransportType,
        endpoint: str,
        sampling_callback=None,
        headers: Optional[Dict[str, str]] = None,
    ) -> BaseTransportManager:
        """
        Create a transport manager for the given protocol type.

        Args:
            transport_type: Which transport protocol to use
            endpoint: MCP server endpoint URL
            sampling_callback: Optional callback for server-initiated sampling
            headers: Optional HTTP headers for authentication

        Returns:
            A fully constructed (but not yet connected) transport manager

        Raises:
            ValueError: If the transport type is not registered
        """
        manager_cls = self._registry.get(transport_type)
        if manager_cls is None:
            supported = ", ".join(t.value for t in self._registry)
            raise ValueError(
                f"Unsupported transport type '{transport_type.value}'. Supported: [{supported}]"
            )

        logger.debug("Creating %s transport for %s", transport_type.value, endpoint)
        return manager_cls(
            endpoint=endpoint,
            sampling_callback=sampling_callback,
            headers=headers,
        )

    @property
    def supported_types(self) -> list:
        """Return the list of currently registered transport types."""
        return list(self._registry.keys())

    def is_supported(self, transport_type: McpTransportType) -> bool:
        """Check whether a given transport type is registered."""
        return transport_type in self._registry
