"""Observation retention and identity are application policy, independent of hosts."""

from lumora.executions.domain.observation import OccurrenceKind, OccurrenceStatus
from lumora.executions.observation import OccurrenceProjection


def test_repeated_sites_have_distinct_occurrences_and_retention_is_explicit():
    view = OccurrenceProjection("run", capacity=2)
    first = view.start("work", OccurrenceKind.OPERATION)
    second = view.start("work", OccurrenceKind.OPERATION)
    before = view.snapshot()
    view.finish(second, OccurrenceStatus.COMPLETED)
    third = view.start("work", OccurrenceKind.OPERATION)
    view.finish(first, OccurrenceStatus.COMPLETED)
    after = view.snapshot()
    assert before.occurrences[1].status == "running"
    assert after.truncated and after.total == 3
    assert [call.ordinal for call in after.occurrences] == [second, third]
    assert after.occurrences[0].status == "completed"
    assert after.revision > before.revision


def test_child_binding_is_separate_from_authored_identity():
    view = OccurrenceProjection("parent")
    call = view.start("body", OccurrenceKind.PROGRAM)
    view.bind_child(call, "actual-child")
    occurrence = view.snapshot().occurrences[0]
    assert occurrence.call_site == "body" and occurrence.child_execution_id == "actual-child"
    assert occurrence.status == "running"
