"""
Abstract base class for MCP transport managers.

Subclasses supply the transport context; this class owns session initialization
and reverse-order cleanup in the task that entered the SDK contexts.
"""

from abc import ABC, abstractmethod
from contextlib import AbstractAsyncContextManager, AsyncExitStack
from typing import Any

from mcp import ClientSession

from plugins.mcp.elements.mcp_server_client.transport.enums import McpTransportType


class McpConnectionError(Exception):
    """Raised when the MCP connection cannot be established or fails."""


class BaseTransportManager(ABC):
    """
    Abstract base for MCP transport managers.

    Orchestrates the full connection lifecycle:
      1) Open a protocol-specific transport context
      2) Create and initialize a ClientSession over that transport
      3) Clean disconnection of both session and transport

    Subclasses supply the transport context and its protocol identity.

    Attributes:
        endpoint: MCP server endpoint URL
        sampling_callback: Optional callback for server-initiated sampling
        headers: Optional HTTP headers for authentication
    """

    def __init__(
        self,
        endpoint: str,
        sampling_callback=None,
        headers: dict[str, str] | None = None,
    ):
        """
        Initialize the transport manager.

        Args:
            endpoint: MCP server endpoint URL
            sampling_callback: Callback for server-initiated sampling requests
            headers: Optional HTTP headers for authentication or custom metadata
        """
        self.endpoint = endpoint
        self.sampling_callback = sampling_callback
        self.headers = headers or {}

        self._session: ClientSession | None = None
        self._is_connected = False
        self._stack: AsyncExitStack | None = None

    # =========================================================================
    # Abstract hooks (subclass-specific)
    # =========================================================================

    @abstractmethod
    def _create_transport_context(self) -> AbstractAsyncContextManager[tuple[Any, Any]]:
        """
        Create the protocol-specific transport context manager (not yet entered).

        Returns:
            An async context manager that yields transport streams
        """

    @property
    @abstractmethod
    def transport_type(self) -> McpTransportType:
        """The transport protocol type this manager implements."""

    # =========================================================================
    # Shared implementation (Template Method)
    # =========================================================================

    @property
    def is_connected(self) -> bool:
        """
        Check if both transport and session are active.

        Returns:
            True if transport is open and ClientSession is initialized
        """
        return self._is_connected and self._session is not None

    async def connect(self) -> None:
        """Open transport/session in this task and unwind failed or cancelled entry."""
        if self.is_connected:
            return
        await self.disconnect()
        try:
            async with AsyncExitStack() as resources:
                read_stream, write_stream = await resources.enter_async_context(
                    self._create_transport_context()
                )
                self._session = ClientSession(
                    read_stream, write_stream, sampling_callback=self.sampling_callback
                )
                await resources.enter_async_context(self._session)
                await self._session.initialize()
                self._stack = resources.pop_all()
        except BaseException as error:
            self._clear_connection()
            if isinstance(error, Exception):
                raise McpConnectionError("MCP connection initialization failed") from error
            raise
        self._is_connected = True

    async def disconnect(self) -> None:
        """Close session before transport, in the task that entered the SDK contexts."""
        resources, self._stack = self._stack, None
        self._is_connected = False
        try:
            if resources is not None:
                await resources.aclose()
        except Exception as error:
            raise McpConnectionError("MCP connection cleanup failed") from error
        finally:
            self._clear_connection()

    def _clear_connection(self) -> None:
        self._session = None
        self._is_connected = False

    # =========================================================================
    # Context manager protocol
    # =========================================================================

    async def __aenter__(self):
        """Connect on entering ``async with`` block."""
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        """Disconnect on exiting ``async with`` block."""
        await self.disconnect()
