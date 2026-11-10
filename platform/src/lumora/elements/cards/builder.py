"""
Backwards-compatibility re-export.
ElementCardBuilder functionality has been replaced by ElementCardService
in lumora.elements.catalog.ports.card_service.
"""

from lumora.elements.catalog.card_service import ElementCardService as ElementCardBuilder

__all__ = ["ElementCardBuilder"]
