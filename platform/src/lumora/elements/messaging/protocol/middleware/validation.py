"""
Validation Middleware for IEM Protocol
"""

from lumora.elements.messaging.protocol.exceptions import IEMValidationException
from lumora.elements.messaging.protocol.interfaces import MessengerMiddleware
from lumora.elements.messaging.protocol.packets import IEMPacket, RequestPacket


class ActionValidationMiddleware(MessengerMiddleware):
    """
    Middleware to validate allowed actions per element type.

    Useful for enforcing API contracts and preventing invalid
    cross-element communication.
    """

    def __init__(self, allowed_actions: dict[str, set[str]]):
        """
        Initialize with action allowlist.

        Args:
            allowed_actions: {element_type: {action1, action2, ...}}
        """
        self._allowed = allowed_actions

    def before_send(self, packet: IEMPacket) -> IEMPacket:
        """Validate outgoing request actions."""
        if isinstance(packet, RequestPacket):
            dst_type = packet.dst.type_key
            if dst_type and dst_type in self._allowed:
                if packet.action not in self._allowed[dst_type]:
                    raise IEMValidationException(
                        f"Action '{packet.action}' not allowed for element type '{dst_type}'"
                    )
        return packet

    def after_receive(self, packet: IEMPacket) -> IEMPacket:
        """Pass through - validation happens on send."""
        return packet


class PayloadValidationMiddleware(MessengerMiddleware):
    """
    Middleware to validate packet payloads against schemas.

    Can be extended to use Pydantic models or JSON schemas
    for validating action arguments and results.
    """

    def __init__(self, schemas: dict[str, any] = None):
        """
        Initialize with payload schemas.

        Args:
            schemas: {action_name: validation_schema}
        """
        self._schemas = schemas or {}

    def before_send(self, packet: IEMPacket) -> IEMPacket:
        """Validate outgoing packet payloads."""
        if isinstance(packet, RequestPacket) and packet.action in self._schemas:
            schema = self._schemas[packet.action]
            # TODO: Implement schema validation
            # For now, just check that args is a dict
            if not isinstance(packet.args, dict):
                raise IEMValidationException(
                    f"Action '{packet.action}' requires dict args, got {type(packet.args)}"
                )
        return packet

    def after_receive(self, packet: IEMPacket) -> IEMPacket:
        """Pass through - validation happens on send."""
        return packet
