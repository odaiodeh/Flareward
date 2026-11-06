"""Graph-local message delivery preserves addressing, acknowledgments and channel contracts."""

from datetime import timedelta

import pytest
from mas.core.enums import ResourceCategory
from mas.core.iem.exceptions import IEMAdjacencyException, IEMValidationException
from mas.core.iem.interfaces import MessengerMiddleware
from mas.core.iem.models import ElementAddress
from mas.core.iem.packets import SystemPacket
from mas.domain.element_card import ElementCard
from mas.graph.messaging import GraphInterMessenger, get_outgoing_targets
from mas.graph.models import AdjacentNodes, StepContext
from mas.graph.state.graph_state import Channel, GraphState
from mas.graph.state.state_view import StateView


def context(uid: str, *targets: str) -> StepContext:
    return StepContext(
        uid=uid,
        adjacent_nodes=AdjacentNodes(
            nodes={
                target: ElementCard(
                    uid=target, category=ResourceCategory.NODE, type_key="test", name=target
                )
                for target in targets
            }
        ),
    )


def packet(src="sender", dst="receiver", **values):
    return SystemPacket(
        src=ElementAddress(uid=src), dst=ElementAddress(uid=dst), system_event="ready", **values
    )


def test_delivery_and_destination_acknowledgment_drive_routing():
    state = GraphState()
    view = StateView(state, reads={Channel.INTER_PACKETS}, writes={Channel.INTER_PACKETS})
    sender_context = context("sender", "receiver", "observer")
    sender = GraphInterMessenger(view, sender_context)
    original = packet()
    identifier = sender.send_packet(original)
    original.system_event = "changed after sending"
    assert get_outgoing_targets(view, sender_context) == {"receiver"}
    observer = GraphInterMessenger(view, context("observer"))
    assert not observer.acknowledge(identifier)
    assert not observer.inbox_packets()
    receiver = GraphInterMessenger(view, context("receiver", "sender"))
    received = receiver.inbox_packets()
    assert [item.system_event for item in received] == ["ready"]
    received[0].system_event = "changed after receiving"
    assert receiver.inbox_packets()[0].system_event == "ready"
    assert receiver.acknowledge(identifier)
    assert receiver.inbox_packets() == [] and get_outgoing_targets(view, sender_context) == set()
    assert not sender.purge() and receiver.purge() == 1


def test_expired_messages_are_neither_delivered_nor_routed():
    state = GraphState(inter_packets=[packet(ttl=timedelta(seconds=-1))])
    view = StateView(state, reads={Channel.INTER_PACKETS}, writes={Channel.INTER_PACKETS})
    assert not GraphInterMessenger(view, context("receiver")).inbox_packets()
    assert not get_outgoing_targets(view, context("sender", "receiver"))
    assert GraphInterMessenger(view, context("receiver")).purge(acked_only=False) == 1


def test_sender_and_destination_scope_are_checked_after_middleware():
    class Redirect(MessengerMiddleware):
        def before_send(self, request):
            request.dst = ElementAddress(uid="outside")
            return request

        def after_receive(self, request):
            return request

    state = GraphState()
    view = StateView(state, reads={Channel.INTER_PACKETS}, writes={Channel.INTER_PACKETS})
    sender = GraphInterMessenger(view, context("sender", "receiver"))
    with pytest.raises(IEMAdjacencyException):
        sender.send_packet(packet(dst="outside"))
    with pytest.raises(IEMValidationException):
        sender.send_packet(packet(src="another-sender"))
    redirected = GraphInterMessenger(view, context("sender", "receiver"), middleware=[Redirect()])
    with pytest.raises(IEMValidationException):
        redirected.send_packet(packet())
    assert not state.inter_packets


def test_broadcast_has_distinct_occurrences_and_cannot_write_a_readonly_view():
    state = GraphState()
    channels = {Channel.INTER_PACKETS}
    sender_context = context("sender", "receiver", "observer")
    sender = GraphInterMessenger(StateView(state, reads=channels, writes=channels), sender_context)
    identifiers = sender.broadcast_packet(packet())
    assert len(identifiers) == len(set(identifiers)) == 2
    assert {item.dst.uid for item in state.inter_packets} == {"receiver", "observer"}
    readonly = GraphInterMessenger(StateView(state, reads=channels, writes=set()), sender_context)
    with pytest.raises(IEMValidationException):
        readonly.send_packet(packet())
    assert len(state.inter_packets) == 2
