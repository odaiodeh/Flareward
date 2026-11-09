"""
A2A Response Handlers Package.

Handlers auto-register via BaseHandler.__init_subclass__.
Handles SUCCESS response types. Errors handled directly by client.

Usage:
    from plugins.a2a.elements.a2a_client.handlers import BaseHandler

    result = BaseHandler.handle(sdk_object)
"""

from plugins.a2a.elements.a2a_client.handlers.base_handler import BaseHandler

# Import handlers to trigger auto-registration
from plugins.a2a.elements.a2a_client.handlers.handlers import (
    ArtifactEventHandler,
    MessageHandler,
    StatusEventHandler,
    TaskHandler,
)

__all__ = [
    "BaseHandler",
    "TaskHandler",
    "MessageHandler",
    "StatusEventHandler",
    "ArtifactEventHandler",
]
