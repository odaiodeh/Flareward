"""
Backwards-compatibility re-export.
ElementCardBuilder functionality has been replaced by ElementCardService
in mas.catalog.card_service.
"""

from mas.application.elements.catalog.card_service import ElementCardService as ElementCardBuilder

__all__ = ["ElementCardBuilder"]
