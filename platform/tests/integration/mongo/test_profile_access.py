"""Real application/HTTP admission filters private targets before creating native work."""

import json

import pytest
from runengine.invocation.config import K8sRunnerConfig
from support.blueprint_http import library_api
from support.blueprints import inline_blueprint
from support.condition_scenarios import routing_graph
from support.conditions import ELEMENT_SPECIFICATIONS
from support.http_programs import execute_program, publish_program
from support.operations import operation_bundle, operation_graph

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.executions.domain.profile_access import (
    OwnerProfileRule,
    ProfileAccessPolicy,
    ProfileGrant,
)
from lumora.executions.models import PreparedExecution
from lumora.programs.domain.bindings import PathBinding
from lumora.programs.domain.models import (
    CustomCoordinatorDefinition,
    GraphDefinition,
    ProgramBody,
    ProgramCallStep,
    ProgramDefinition,
)
from lumora.services.identity.domain import Identity


@pytest.fixture
def restricted_settings(secret_settings):
    return secret_settings.model_copy(
        update={
            "library": True,
            "application_modules": ("support.programs",),
            "execution_profiles": {
                **secret_settings.execution_profiles,
                "admin-only": K8sRunnerConfig(
                    image="private-registry/privileged-image",
                    env={"PRIVATE_SETTING": "private-target-value"},
                ),
            },
            "profile_access": ProfileAccessPolicy(
                owners=(
                    OwnerProfileRule(
                        owner=Identity.user("owner"),
                        grant=ProfileGrant(profiles=("process",), default_profile="process"),
                    ),
                )
            ),
        }
    )


async def test_owner_catalog_and_preview_use_the_same_restricted_default(restricted_settings):
    async with library_api(restricted_settings, Identity.user("owner")) as http:
        catalog = await http.get("/api/catalog/execution-profiles")
        assert catalog.status_code == 200 and catalog.json() == {
            "profiles": ["process"],
            "default_profile": "process",
            "environment_profiles": [],
        }
        spec = inline_blueprint().model_dump(mode="json")
        allowed = await http.post("/api/blueprints/draft/placement", json={"spec": spec})
        assert allowed.status_code == 200, allowed.text
        assert allowed.json()["default_profile"] == "process"
        spec["execution_profile"] = "admin-only"
        denied = await http.post("/api/blueprints/draft/placement", json={"spec": spec})
        assert denied.status_code == 403 and "private-target-value" not in denied.text
    async with library_api(restricted_settings, Identity.team("owner")) as http:
        assert (await http.get("/api/catalog/execution-profiles")).status_code == 403


@pytest.mark.parametrize("boundary", ["step", "condition", "environment", "pinned", "inline"])
async def test_forbidden_profile_at_any_static_scope_refuses_before_execution_record(
    application, restricted_settings, mongo_database, boundary
):
    for spec in ELEMENT_SPECIFICATIONS:
        application.elements.register_spec_class(spec)
    owner = Identity.user("owner")
    async with library_api(restricted_settings, owner, elements=application.elements) as http:
        if boundary in {"step", "environment"}:
            graph = operation_graph("process")
            selection = (
                ExecutionSelection(profile="admin-only")
                if boundary == "step"
                else ExecutionSelection(environment="workspace")
            )
            implementation = graph.model_copy(
                update={
                    "steps": (graph.steps[0].model_copy(update={"execution": selection}),),
                    "environments": {"workspace": "admin-only"}
                    if boundary == "environment"
                    else {},
                }
            )
        elif boundary == "condition":
            implementation = routing_graph(
                "router_boolean",
                {"type": "router_boolean", "boolean_value": True},
                profile="admin-only",
            )
        else:
            child = ProgramBody(
                implementation=CustomCoordinatorDefinition(implementation="greeting", version="1"),
                execution_profile="admin-only",
            )
            if boundary == "pinned":
                target = await publish_program(
                    http,
                    ProgramDefinition(
                        program_id="child", name="child", owner=owner, **child.model_dump()
                    ),
                )
                implementation = CustomCoordinatorDefinition(
                    implementation="composed", version="1", children={"greet": target}
                )
            else:
                implementation = GraphDefinition(
                    steps=(
                        ProgramCallStep(
                            uid="child", program=child, inputs=PathBinding(path=("input",))
                        ),
                    ),
                    entry="child",
                    exit="child",
                )
        reference = await publish_program(
            http,
            ProgramDefinition(
                program_id="root", name="root", owner=owner, implementation=implementation
            ),
        )
        denied = await http.post(
            "/api/executions",
            json={
                "program": reference.model_dump(mode="json"),
                "execution_id": "refused",
                "inputs": {"name": "private-input"},
            },
        )
        assert denied.status_code == 403, denied.text
        assert not any(
            value in denied.text
            for value in ("private-input", "private-target-value", "private-registry")
        )
        assert await mongo_database.program_executions.count_documents({}) == 0


async def test_admitted_backend_profiles_are_filtered_frozen_and_visible_as_safe_metadata(
    application, restricted_settings, mongo_database
):
    owner = Identity.user("owner")
    body = CustomCoordinatorDefinition(
        implementation="placed_operation",
        version="1",
        config={"bundle": operation_bundle(application.elements).model_dump(mode="json")},
    )
    async with library_api(restricted_settings, owner, elements=application.elements) as http:
        revision = await publish_program(
            http,
            ProgramDefinition(program_id="root", name="root", owner=owner, implementation=body),
        )
        result = await execute_program(http, revision, "admitted", {"text": "allowed"})
        assert result["phase"] == "completed", result["failure"]
        assert result["result"] == {
            "text": "typed:middle:allowed",
            "execution_id": "admitted",
            "key": "work",
        }
        assert result["admitted_profiles"] == {
            "profiles": ["process"],
            "default_profile": "process",
            "environment_profiles": [],
        }
        document = await mongo_database.program_executions.find_one({"_id": "admitted"})
        prepared = PreparedExecution.model_validate_json(document["prepared"])
        assert tuple(json.loads(prepared.payload_json)["input"]["placement"]["profiles"]) == (
            "process",
        )
        assert (
            "private-target-value" not in prepared.payload_json
            and "private-registry" not in prepared.payload_json
        )
        assert prepared.admitted_profiles.model_dump(mode="json") == result["admitted_profiles"]
        dynamic = body.model_copy(
            update={"config": {**body.config, "execution": {"profile": "admin-only"}}}
        )
        revision = await publish_program(
            http,
            ProgramDefinition(
                program_id="dynamic", name="dynamic", owner=owner, implementation=dynamic
            ),
        )
        denied = await execute_program(http, revision, "dynamic-denied", {"text": "private-input"})
        assert denied["phase"] == "failed" and denied["failure"]["kind"] == "contract"
        assert denied["failure"]["code"] == "placement_refused"
        assert "private-input" not in denied["failure"]["message"]
