"""
Backwards-compatibility re-export.
ElementCardBuilder functionality has been replaced by ElementCardService
in flareward.elements.catalog.ports.card_service.
"""

from flareward.elements.catalog.card_service import ElementCardService as ElementCardBuilder

__all__ = ["ElementCardBuilder"]
