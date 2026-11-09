"""
A2A Provider Package.

Provides clean interface for communicating with A2A (Agent-to-Agent) protocol agents.
Uses official a2a-sdk internally with extensible handler system.
"""

from plugins.a2a.elements.a2a_client.a2a_provider_factory import A2AProviderFactory
from plugins.a2a.elements.a2a_client.client import (
    A2AClient,
    A2AClientError,
    A2AConnectionError,
)
from plugins.a2a.elements.a2a_client.config import A2AProviderConfig
from plugins.a2a.elements.a2a_client.converter import (
    A2AConverter,
    ConversionResult,
    FileInfo,
)
from plugins.a2a.elements.a2a_client.handlers import (
    ArtifactEventHandler,
    BaseHandler,
    MessageHandler,
    StatusEventHandler,
    TaskHandler,
)
from plugins.a2a.elements.a2a_client.identifiers import META, Identifier
from plugins.a2a.elements.a2a_client.provider import (
    A2AProvider,
    A2ATaskError,
    A2ATimeoutError,
)
from plugins.a2a.elements.a2a_client.result import A2AResult, ResultKind

__all__ = [
    "A2AProvider",
    "A2AProviderFactory",
    "A2AClient",
    "A2AClientError",
    "A2AConnectionError",
    "A2ATaskError",
    "A2ATimeoutError",
    "A2AConverter",
    "ConversionResult",
    "FileInfo",
    "A2AResult",
    "ResultKind",
    "A2AProviderConfig",
    "Identifier",
    "META",
    "BaseHandler",
    "TaskHandler",
    "MessageHandler",
    "StatusEventHandler",
    "ArtifactEventHandler",
]
