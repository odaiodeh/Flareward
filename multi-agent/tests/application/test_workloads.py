"""Workload hierarchy/content services operate through an injected storage port."""

from mas.application.agents.delegation_policy import PermissiveDelegationPolicy
from mas.application.workloads.streaming_hook import WorkPlanStreamingHook
from mas.application.workloads.unified_service import UnifiedWorkloadService
from support.workloads import MemoryWorkloadStorage, workload_contract


def test_workload_services_without_a_graph():
    workload_contract(MemoryWorkloadStorage())


def test_delegation_policy_accepts_plain_candidates_and_snapshots_membership():
    candidates = {"research": object(), "review": object()}
    policy = PermissiveDelegationPolicy(candidates)
    candidates["later"] = object()
    assert policy.filter_delegable_nodes(candidates) == {
        key: value for key, value in candidates.items() if key != "later"
    }
    assert not policy.is_delegable("missing")


def test_workplan_hooks_are_injected_without_graph_or_node_context():
    services = UnifiedWorkloadService(MemoryWorkloadStorage())
    thread = services.get_thread_service().create_root_thread("Build", "Deliver", "agent")
    workspaces = services.get_workspace_service()
    events = []
    workspaces.add_workplan_hook(WorkPlanStreamingHook(events.append))
    plan = workspaces.create_work_plan(thread.thread_id, "agent", "Implement")
    assert workspaces.save_work_plan(plan)
    assert workspaces.load_work_plan(thread.thread_id, "agent") == plan
    assert [event["action"] for event in events] == ["saved", "loaded"]
