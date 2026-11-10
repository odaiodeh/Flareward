"""
IEM Protocol Interfaces

Defines the core interfaces for Inter-Element Messaging.
Clean generic packet handling with extensible packet types.
"""

from abc import ABC, abstractmethod
from datetime import timedelta
from typing import List

from lumora.elements.messaging.protocol.models import PacketType
from lumora.elements.messaging.protocol.packets import BaseIEMPacket


class InterMessenger(ABC):
    """
    Core interface for inter-element messaging.

    Clean generic packet handling with support for any packet type.
    Provides transport layer services: sending, receiving, acknowledgment.
    """

    # === CORE PACKET OPERATIONS ===
    @abstractmethod
    def send_packet(self, packet: BaseIEMPacket) -> str:
        """
        Send any packet via IEM.

        Args:
            packet: Packet to send

        Returns:
            Packet ID for tracking

        Raises:
            IEMAdjacencyException: If destination is not adjacent (when enforced)
            IEMValidationException: If packet validation fails
        """
        pass

    @abstractmethod
    def inbox_packets(self, packet_type: PacketType = None) -> List[BaseIEMPacket]:
        """
        Get unacknowledged packets addressed to this element.

        Args:
            packet_type: Filter by packet type, or None for all types

        Returns:
            List of unacknowledged packets
        """
        pass

    @abstractmethod
    def acknowledge(self, packet_id: str) -> bool:
        """
        Mark a packet as acknowledged.

        Args:
            packet_id: ID of packet to acknowledge

        Returns:
            True if packet was found and acknowledged
        """
        pass

    @abstractmethod
    def broadcast_packet(self, packet: BaseIEMPacket) -> List[str]:
        """
        Broadcast packet to all adjacent nodes.

        Args:
            packet: Packet to broadcast (dst will be overridden)

        Returns:
            List of packet IDs sent
        """
        pass

    @abstractmethod
    def multicast_packet(self, packet: BaseIEMPacket, target_uids: List[str]) -> List[str]:
        """
        Send packet to multiple specific nodes.

        Args:
            packet: Packet to send (dst will be overridden for each target)
            target_uids: List of target node UIDs

        Returns:
            List of packet IDs sent
        """
        pass

    # === UTILITY OPERATIONS ===
    @abstractmethod
    def purge(self, *, max_age: timedelta = None, acked_only: bool = True) -> int:
        """
        Remove old/acknowledged packets from the state.

        Args:
            max_age: Remove packets older than this (None = use messenger default)
            acked_only: Only remove acknowledged packets

        Returns:
            Number of packets removed
        """
        pass


class MessengerMiddleware(ABC):
    """
    Middleware interface for intercepting and modifying IEM packets.

    Allows for cross-cutting concerns like validation, logging,
    security checks, etc.
    """

    @abstractmethod
    def before_send(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        """
        Called before sending a packet.

        Args:
            packet: Packet about to be sent

        Returns:
            Modified packet (or same packet)

        Raises:
            IEMException: To prevent sending
        """
        pass

    @abstractmethod
    def after_receive(self, packet: BaseIEMPacket) -> BaseIEMPacket:
        """
        Called after receiving a packet.

        Args:
            packet: Packet that was received

        Returns:
            Modified packet (or same packet)

        Raises:
            IEMException: To reject packet
        """
        pass
