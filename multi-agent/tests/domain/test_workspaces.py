"""Persisted workspace values retain typed results, artifacts, variables and retry limits."""

from mas.domain.workloads import AgentResult, WorkItem, Workspace, WorkspaceArtifact


def test_workspace_roundtrip_preserves_the_context_used_by_all_accessors():
    workspace = Workspace.create("conversation")
    workspace.set_variable("answer", 42)
    result = AgentResult(content="verified", agent_id="researcher", agent_name="Researcher")
    workspace.add_result(result)
    workspace.add_artifact("report", "document", "reports/result.txt", "researcher")
    restored = Workspace.model_validate_json(workspace.model_dump_json())

    assert restored.has_variable("answer") and restored.get_variable("answer") == 42
    assert restored.get_latest_result() == result
    assert restored.get_results_by_agent("researcher") == [result]
    artifacts = restored.get_artifact_by_type("document")
    assert len(artifacts) == 1 and isinstance(artifacts[0], WorkspaceArtifact)
    assert artifacts[0].location == "reports/result.txt"
    assert restored.get_context_summary()["variables_count"] == 1
    assert Workspace.create("empty").get_latest_result() is None


def test_work_item_retry_budget_survives_serialization_without_an_application_service():
    item = WorkItem(id="lookup", title="Lookup", description="Read evidence", max_retries=2)
    assert item.increment_retry()
    restored = WorkItem.model_validate_json(item.model_dump_json())
    assert restored.can_retry() and restored.retry_count == 1
    assert restored.increment_retry()
    assert not restored.can_retry() and not restored.increment_retry()
    assert restored.retry_count == 2
