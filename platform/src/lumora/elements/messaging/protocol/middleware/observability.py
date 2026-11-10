"""
Observability Middleware for IEM Protocol
"""

import logging

from lumora.elements.messaging.protocol.interfaces import MessengerMiddleware
from lumora.elements.messaging.protocol.packets import IEMPacket

logger = logging.getLogger(__name__)


class LoggingMiddleware(MessengerMiddleware):
    """
    Middleware to log IEM packet flow for debugging and monitoring.
    """

    def __init__(self, log_level: int = logging.INFO):
        """
        Initialize logging middleware.

        Args:
            log_level: Logging level for packet events
        """
        self.log_level = log_level

    def before_send(self, packet: IEMPacket) -> IEMPacket:
        """Log outgoing packets."""
        logger.log(
            self.log_level,
            f"IEM Send: {packet.src.uid} -> {packet.dst.uid} "
            f"[{packet.kind}] {getattr(packet, 'action', getattr(packet, 'event_type', 'N/A'))}",
        )
        return packet

    def after_receive(self, packet: IEMPacket) -> IEMPacket:
        """Log incoming packets."""
        logger.log(
            self.log_level,
            f"IEM Recv: {packet.src.uid} -> {packet.dst.uid} "
            f"[{packet.kind}] {getattr(packet, 'action', getattr(packet, 'event_type', 'N/A'))}",
        )
        return packet


class MetricsMiddleware(MessengerMiddleware):
    """
    Middleware to collect metrics on IEM usage.

    Tracks packet counts, response times, error rates, etc.
    """

    def __init__(self):
        """Initialize metrics collection."""
        self.packet_counts = {}
        self.error_counts = {}

    def before_send(self, packet: IEMPacket) -> IEMPacket:
        """Count outgoing packets."""
        key = f"{packet.kind}:send"
        self.packet_counts[key] = self.packet_counts.get(key, 0) + 1
        return packet

    def after_receive(self, packet: IEMPacket) -> IEMPacket:
        """Count incoming packets."""
        key = f"{packet.kind}:recv"
        self.packet_counts[key] = self.packet_counts.get(key, 0) + 1

        # Track errors in response packets
        if hasattr(packet, "error") and packet.error:
            error_key = f"error:{packet.error.code}"
            self.error_counts[error_key] = self.error_counts.get(error_key, 0) + 1

        return packet

    def get_stats(self) -> dict:
        """Get collected statistics."""
        return {
            "packet_counts": self.packet_counts.copy(),
            "error_counts": self.error_counts.copy(),
        }
