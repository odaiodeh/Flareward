"""Discover coordinator contracts before binding targets, without executing authoring effects."""

import pytest

from lumora.programs.authoring import ProgramIssueCode
from lumora.programs.composition.programs import COORDINATORS
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramDefinition,
    ProgramRef,
)
from lumora.programs.service import ProgramContractError


@pytest.fixture(autouse=True)
def installed_controls(application):
    for registration in COORDINATORS:
        application.applications.register(registration)


@pytest.mark.parametrize(
    "implementation,config,names",
    [
        ("map", {}, {"body"}),
        ("repeat", {"body": "attempt"}, {"attempt"}),
        (
            "choose",
            {"branches": {"approved": "release", "rejected": "repair"}},
            {"release", "repair"},
        ),
        ("wait", {"channel": "review"}, set()),
    ],
)
async def test_preview_discovers_configured_dependencies_before_binding_or_saving(
    application, implementation, config, names
):
    body = ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation=implementation, version="1", config=config
        )
    )
    preview = application.programs.preview_interface(body)
    assert not preview.issues
    assert set(preview.interface.dependencies) == names
    assert not preview.interface.children
    assert not (await application.programs.list(application.owner)).programs


async def test_preview_does_not_resolve_target_authority_or_owned_configuration(application):
    body = ProgramBody(
        implementation=CustomCoordinatorDefinition(
            implementation="map",
            version="1",
            children={
                "body": ProgramRef(program_id="unavailable", revision=5),
                "owned": ProgramBody(
                    implementation=CustomCoordinatorDefinition(
                        implementation="not-installed", version="1"
                    )
                ),
            },
        )
    )
    preview = application.programs.preview_interface(body)
    assert not preview.issues and set(preview.interface.dependencies) == {"body"}
    assert "unavailable" not in preview.model_dump_json()
    assert "not-installed" not in preview.model_dump_json()


async def test_preview_does_not_replace_missing_binding_publication_checks(application):
    definition = ProgramDefinition(
        program_id="unbound",
        name="Unbound",
        owner=application.owner,
        implementation=CustomCoordinatorDefinition(implementation="map", version="1"),
    )
    assert application.programs.preview_interface(definition).interface is not None
    draft = await application.programs.save(definition, application.owner)
    report = await application.programs.validate(
        "unbound", application.owner, expected_version=draft.version
    )
    assert not report.valid
    assert report.issues[0].code == ProgramIssueCode.BINDING
    assert report.issues[0].path == ("implementation", "children", "body")
    with pytest.raises(ProgramContractError, match="not bound"):
        await application.programs.publish(
            "unbound", application.owner, expected_version=draft.version
        )


@pytest.mark.parametrize(
    "config", [{"max_items": "private-invalid-value"}, {"unexpected": "private-value"}]
)
def test_invalid_configuration_is_a_safe_preview_diagnostic(application, config):
    body = ProgramBody(
        implementation=CustomCoordinatorDefinition(implementation="map", version="1", config=config)
    )
    preview = application.programs.preview_interface(body)
    assert preview.interface is None and preview.issues
    assert "private" not in preview.model_dump_json()


def test_native_graph_preview_does_not_require_complete_topology(application):
    preview = application.programs.preview_interface(
        ProgramBody(implementation=GraphDefinition(steps=()))
    )
    assert not preview.issues and preview.interface.coordinator.key == "graph"


def test_incomplete_coordinator_configuration_does_not_fabricate_dependencies(application):
    preview = application.programs.preview_interface(
        ProgramBody(
            implementation=CustomCoordinatorDefinition(implementation="choose", version="1")
        )
    )
    assert preview.interface is None and preview.issues
