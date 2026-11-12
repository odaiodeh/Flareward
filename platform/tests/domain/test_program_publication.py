"""Published definitions enforce completeness independently of service adapters."""

import pytest
from pydantic import ValidationError
from support.program_interfaces import declared_interface

from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramCallStep,
    ProgramDefinition,
    ProgramRevision,
)
from lumora.services.identity.domain import Identity


@pytest.mark.parametrize(
    "implementation",
    [
        GraphDefinition(steps=()),
        CustomCoordinatorDefinition(
            implementation="installed",
            version="1",
            child_environment_imports={"unbound": {"workspace": "shared"}},
        ),
    ],
)
def test_drafts_round_trip_but_incomplete_revisions_are_rejected(implementation):
    draft = ProgramDefinition(
        program_id="draft",
        name="Draft",
        owner=Identity.user("owner"),
        implementation=implementation,
    )
    assert ProgramDefinition.model_validate_json(draft.model_dump_json()) == draft
    with pytest.raises(ValidationError):
        ProgramRevision(definition=draft, revision=1, interface=declared_interface(draft))


def test_copied_mutable_content_cannot_bypass_published_identity_invariants():
    step = ProgramCallStep(uid="work", program={"program_id": "child", "revision": 1})
    graph = GraphDefinition(steps=(step,), entry="work", exit="work")
    definition = ProgramDefinition(
        program_id="copied",
        name="Copied",
        owner=Identity.user("owner"),
        implementation=graph,
    )
    copied = definition.model_copy(
        update={"implementation": graph.model_copy(update={"steps": (step, step)})}
    )
    with pytest.raises(ValidationError, match="unique"):
        ProgramRevision(definition=copied, revision=1, interface=declared_interface(copied))
