"""Graph channels adapt the same workload service contract and preserve saved values."""

from mas.graph.state.graph_state import Channel, GraphState
from mas.graph.state.state_view import StateView
from mas.graph.workloads import GraphWorkloadStorage
from support.workloads import workload_contract


def test_closed_channel_names_cover_the_base_graph_state():
    assert {channel.value for channel in Channel} == set(GraphState.model_fields)


def test_workload_services_through_graph_channels():
    state = GraphState()
    channels = {Channel.THREADS, Channel.WORKSPACES}
    storage = GraphWorkloadStorage(StateView(state, reads=channels, writes=channels))
    workload_contract(storage)
    restored = GraphState.model_validate_json(state.model_dump_json())
    rebound = GraphWorkloadStorage(StateView(restored, reads=channels, writes=channels))
    assert rebound.list_threads() == storage.list_threads()
    for thread in storage.list_threads():
        assert rebound.get_workspace(thread.thread_id) == storage.get_workspace(thread.thread_id)
