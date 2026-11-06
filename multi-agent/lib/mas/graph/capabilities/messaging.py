"""Graph nodes bind the portable messaging interface to restricted graph state."""

import logging

from mas.application.programs.graph_elements import SupportsStateContext
from mas.core.iem.interfaces import InterMessenger
from mas.core.iem.models import ElementAddress, PacketType
from mas.core.iem.packets import BaseIEMPacket, TaskPacket
from mas.domain.workloads.task import Task
from mas.graph.messaging import GraphInterMessenger, get_outgoing_targets
from mas.graph.state.graph_state import Channel

logger = logging.getLogger(__name__)


class GraphMessagingMixin[T: SupportsStateContext]:
    """Mixin for nodes that use the IEM protocol."""

    # Channel permissions (inherited by MRO)
    MIXIN_READS = {Channel.INTER_PACKETS}
    MIXIN_WRITES = {Channel.INTER_PACKETS}

    def __init_subclass__(cls) -> None:
        """Ensure the concrete class implements required protocols."""
        if not issubclass(cls, SupportsStateContext):
            raise TypeError(
                f"{cls.__name__} requires state/context support (get_state() + get_context())."
            )
        super().__init_subclass__()

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

    def get_messenger(self: T) -> InterMessenger:
        """Get IEM messenger bound to current state."""
        try:
            state = self.get_state()
            context = self.get_context()
        except RuntimeError:
            raise RuntimeError("IEM messenger not available outside of run()")

        return GraphInterMessenger(state, context)

    @property
    def ms(self: T) -> InterMessenger:
        """Access to IEM messenger - creates fresh instance with current state."""
        return self.get_messenger()

    @property
    def messenger(self: T) -> InterMessenger:
        """Alias for ms property."""
        return self.ms

    # === GENERIC PACKET OPERATIONS ===
    def send_packet(self, packet: BaseIEMPacket) -> str:
        """Send any packet via IEM."""
        return self.ms.send_packet(packet)

    def broadcast_packet(self, packet: BaseIEMPacket) -> list[str]:
        """Broadcast packet to all adjacent nodes."""
        return self.ms.broadcast_packet(packet)

    def multicast_packet(self, packet: BaseIEMPacket, target_uids: list[str]) -> list[str]:
        """Send packet to multiple specific nodes (multicast)."""
        return self.ms.multicast_packet(packet, target_uids)

    def reply_packet(self, original_packet: BaseIEMPacket, reply_packet: BaseIEMPacket) -> str:
        """Reply to packet with another packet."""
        reply_packet.dst = original_packet.src
        return self.send_packet(reply_packet)

    def inbox_packets(self, packet_type: PacketType = None) -> list[BaseIEMPacket]:
        """Get incoming packets, optionally filtered by type."""
        return self.ms.inbox_packets(packet_type)

    async def process_packets(self) -> None:
        """Process all incoming packets."""
        for packet in self.inbox_packets():
            try:
                await self.handle_packet(packet)
            finally:
                self.acknowledge(packet.id)

    async def handle_packet(self, packet: BaseIEMPacket) -> None:
        """Handle incoming packet based on type."""
        if packet.type == PacketType.TASK:
            await self.handle_task_packet(packet)
        elif packet.type == PacketType.SYSTEM:
            await self.handle_system_packet(packet)
        elif packet.type == PacketType.DEBUG:
            await self.handle_debug_packet(packet)
        else:
            logger.warning("iem.unknown_packet_type", extra={"packet_type": packet.type})

    # === PACKET TYPE HANDLERS (Override in subclasses) ===
    async def handle_task_packet(self, packet: BaseIEMPacket) -> None:
        """Override to handle task packets."""
        pass

    async def handle_system_packet(self, packet: BaseIEMPacket) -> None:
        """Override to handle system packets."""
        pass

    async def handle_debug_packet(self, packet: BaseIEMPacket) -> None:
        """Override to handle debug packets."""
        pass

    # === TASK OPERATIONS ===
    def send_task(self: T, dst: str, task: Task) -> str:
        """Send task to specific node."""
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid), dst=ElementAddress(uid=dst), task=task
        )
        return self.send_packet(packet)

    def broadcast_task(self: T, task: Task) -> list[str]:
        """Broadcast task to all adjacent nodes."""
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=ElementAddress(uid=""),  # Will be overridden in broadcast
            task=task,
        )
        return self.broadcast_packet(packet)

    def multicast_task(self: T, task: Task, target_uids: list[str]) -> list[str]:
        """Send task to multiple specific nodes (multicast)."""
        packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=ElementAddress(uid=""),  # Will be overridden in multicast
            task=task,
        )
        return self.multicast_packet(packet, target_uids)

    def reply_task(self: T, original_packet: BaseIEMPacket, response_task: Task) -> str:
        """Reply to packet with task."""
        reply_packet = TaskPacket.create(
            src=ElementAddress(uid=self.get_context().uid),
            dst=original_packet.src,
            task=response_task,
        )
        return self.send_packet(reply_packet)

    # === UTILITIES ===
    def acknowledge(self, packet_id: str) -> bool:
        """Acknowledge packet. Delegates to messenger."""
        return self.ms.acknowledge(packet_id)

    def purge(self, **kwargs) -> int:
        """Purge old packets from state. Delegates to messenger."""
        return self.ms.purge(**kwargs)

    def has_outgoing_packets(self: T) -> bool:
        """Check if this node has sent unacknowledged packets to adjacent nodes."""
        try:
            state = self.get_state()
            context = self.get_context()
            targets = get_outgoing_targets(state, context)
            return len(targets) > 0
        except RuntimeError:
            # Called outside of run() - no packets can exist
            return False

    def get_outgoing_targets(self: T) -> set[str]:
        """Get UIDs of adjacent nodes that have unacknowledged packets from this node."""
        try:
            state = self.get_state()
            context = self.get_context()
            return get_outgoing_targets(state, context)
        except RuntimeError:
            # Called outside of run() - return empty set
            return set()
