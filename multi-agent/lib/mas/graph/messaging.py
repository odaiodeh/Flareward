"""Graph-state transport implements the portable inter-element messaging contract."""

from collections.abc import Sequence
from datetime import UTC, datetime, timedelta
from uuid import uuid4

from mas.core.iem.exceptions import IEMAdjacencyException, IEMException, IEMValidationException
from mas.core.iem.interfaces import InterMessenger, MessengerMiddleware
from mas.core.iem.models import ElementAddress, PacketType
from mas.core.iem.packets import BaseIEMPacket
from mas.graph.models.step_context import StepContext
from mas.graph.state.graph_state import Channel
from mas.graph.state.state_view import StateView


class GraphInterMessenger(InterMessenger):
    def __init__(
        self,
        state: StateView,
        context: StepContext,
        *,
        middleware: Sequence[MessengerMiddleware] = (),
        max_packet_age: timedelta = timedelta(hours=24),
    ) -> None:
        self._state, self._uid = state, context.uid
        self._adjacent = frozenset(context.adjacent_nodes)
        self._middleware, self._max_packet_age = tuple(middleware), max_packet_age

    def send_packet(self, packet: BaseIEMPacket) -> str:
        if packet.dst.uid not in self._adjacent:
            raise IEMAdjacencyException("Packet destination is not adjacent")
        try:
            prepared = packet.model_copy(deep=True)
            for middleware in self._middleware:
                prepared = middleware.before_send(prepared)
            if prepared.src.uid != self._uid or prepared.dst.uid not in self._adjacent:
                raise IEMValidationException("Packet exceeds its sender or destination scope")
            self._state[Channel.INTER_PACKETS] = [
                *self._state.get(Channel.INTER_PACKETS, []),
                prepared,
            ]
            return prepared.id
        except IEMException:
            raise
        except Exception:
            raise IEMValidationException("Packet could not be sent") from None

    def inbox_packets(self, packet_type: PacketType | None = None) -> list[BaseIEMPacket]:
        received = []
        for packet in self._state.get(Channel.INTER_PACKETS, []):
            if (
                packet.dst.uid != self._uid
                or (packet_type is not None and packet.type != packet_type)
                or packet.is_acknowledged_by(self._uid)
                or packet.is_expired
            ):
                continue
            try:
                prepared = packet.model_copy(deep=True)
                for middleware in self._middleware:
                    prepared = middleware.after_receive(prepared)
                received.append(prepared)
            except IEMException:
                continue
        return received

    def acknowledge(self, packet_id: str) -> bool:
        packets = list(self._state.get(Channel.INTER_PACKETS, []))
        for index, packet in enumerate(packets):
            if packet.id == packet_id and packet.dst.uid == self._uid:
                acknowledged = packet.model_copy(deep=True)
                acknowledged.acknowledge(self._uid)
                packets[index] = acknowledged
                self._state[Channel.INTER_PACKETS] = packets
                return True
        return False

    def purge(self, *, max_age: timedelta | None = None, acked_only: bool = True) -> int:
        packets = self._state.get(Channel.INTER_PACKETS, [])
        now, age = datetime.now(UTC), max_age if max_age is not None else self._max_packet_age
        retained = [
            packet
            for packet in packets
            if not (
                packet.dst.uid == self._uid
                and (
                    packet.is_acknowledged_by(self._uid)
                    if acked_only
                    else packet.is_expired or now - packet.ts > age
                )
            )
        ]
        if len(retained) != len(packets):
            self._state[Channel.INTER_PACKETS] = retained
        return len(packets) - len(retained)

    def broadcast_packet(self, packet: BaseIEMPacket) -> list[str]:
        return self.multicast_packet(packet, sorted(self._adjacent))

    def multicast_packet(self, packet: BaseIEMPacket, target_uids: list[str]) -> list[str]:
        identifiers = []
        for uid in target_uids:
            addressed = packet.model_copy(
                update={"id": str(uuid4()), "dst": ElementAddress(uid=uid)}, deep=True
            )
            try:
                identifiers.append(self.send_packet(addressed))
            except IEMException:
                continue
        return identifiers


def get_outgoing_targets(state: StateView, context: StepContext) -> set[str]:
    return {
        packet.dst.uid
        for packet in state.get(Channel.INTER_PACKETS, [])
        if packet.src.uid == context.uid
        and packet.dst.uid in context.adjacent_nodes
        and not packet.is_acknowledged_by(packet.dst.uid)
        and not packet.is_expired
    }
