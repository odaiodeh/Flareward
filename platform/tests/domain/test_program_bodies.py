"""Owned bodies freeze inside one revision and are addressed by authored identities."""

import pytest
from pydantic import ValidationError

from flareward.programs.domain.models import (
    ApplicationDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ProgramDefinition,
    ProgramImplementation,
    ProgramRef,
    ProgramRevision,
)
from flareward.services.identity.domain import Identity


def body() -> ProgramBody:
    return ProgramBody(implementation=ApplicationDefinition(implementation="greeting", version="1"))


def definition(implementation: ProgramImplementation) -> ProgramDefinition:
    return ProgramDefinition(
        program_id="owner",
        name="Owner",
        owner=Identity.user("alice"),
        implementation=implementation,
    )


def test_owned_graph_and_backend_bodies_round_trip_in_one_published_revision():
    leaf = body()
    control = ProgramBody(
        implementation=ApplicationDefinition(
            implementation="map", version="1", children={"body": leaf}
        )
    )
    root = definition(
        GraphDefinition(
            steps=(ProgramCallStep(uid="items", program=control),), entry="items", exit="items"
        )
    )
    revision = ProgramRevision(definition=root, revision=1)
    restored = ProgramRevision.model_validate_json(revision.model_dump_json())
    assert restored == revision
    assert restored.definition.body_at(("items", "body")) == leaf
    assert restored.reference == ProgramRef(program_id="owner", revision=1)
    assert "program_id" not in leaf.model_dump()
    assert "owner" not in control.model_dump()


def test_body_addresses_use_authored_names_and_do_not_cross_published_references():
    owned = body()
    root = definition(
        GraphDefinition(
            steps=(
                ProgramCallStep(uid="local", program=owned),
                ProgramCallStep(
                    uid="published", program=ProgramRef(program_id="other", revision=2)
                ),
            ),
            entry="local",
            exit="published",
        )
    )
    graph = root.implementation
    assert isinstance(graph, GraphDefinition)
    reordered = root.model_copy(
        update={"implementation": graph.model_copy(update={"steps": tuple(reversed(graph.steps))})}
    )
    assert reordered.body_at(("local",)) == owned
    for path in (("missing",), ("published",), ("published", "local")):
        with pytest.raises(ValueError, match="Owned body path"):
            root.body_at(path)


@pytest.mark.parametrize("slot", ["graph", "backend"])
def test_independent_definition_cannot_silently_become_an_owned_body(slot):
    root = definition(body().implementation)
    with pytest.raises(ValidationError, match="published reference"):
        if slot == "graph":
            ProgramCallStep(uid="call", program=root)
        else:
            ApplicationDefinition(implementation="map", version="1", children={"body": root})
    with pytest.raises(ValidationError):
        ProgramBody.model_validate({**body().model_dump(), "owner": root.owner.model_dump()})


def test_incomplete_nested_body_is_a_draft_but_not_an_executable_revision():
    root = definition(
        ApplicationDefinition(
            implementation="map",
            version="1",
            children={"body": ProgramBody(implementation=GraphDefinition(steps=()))},
        )
    )
    assert ProgramDefinition.model_validate_json(root.model_dump_json()) == root
    with pytest.raises(ValidationError, match="entry and exit"):
        ProgramRevision(definition=root, revision=1)


def test_owned_edits_change_the_enclosing_revision_digest():
    first = definition(
        ApplicationDefinition(implementation="map", version="1", children={"body": body()})
    )
    edited = definition(
        ApplicationDefinition(implementation="map", version="1", children={"other": body()})
    )
    assert (
        ProgramRevision(definition=first, revision=1).content_digest
        != ProgramRevision(definition=edited, revision=1).content_digest
    )
