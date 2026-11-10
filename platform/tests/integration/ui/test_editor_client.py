"""UI contracts and production clients share the installed TypeScript runner."""

import asyncio
import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest
from pydantic import SecretStr
from runengine.adapters.coordination.config import TemporalHostConfig
from runengine.invocation.config import K8sRunnerConfig
from support.calendar import CalendarDeployment
from support.http_programs import publish_program
from support.managed_access import managed_access_api
from support.review_api import review_api
from support.review_programs import review_definition, review_graph
from support.server import api_process
from support.sharing import invitation
from support.ui_clients import run_contracts
from temporalio.client import Client

from lumora.async_work import await_owned
from lumora.bootstrap.settings.interaction_settings import InteractionBackend
from lumora.bootstrap.settings.worker_settings import WorkerSettings
from lumora.executions.domain.budgets import WorkLimits
from lumora.executions.domain.profile_access import (
    OwnerProfileRule,
    ProfileAccessPolicy,
    ProfileGrant,
)
from lumora.programs.domain.models import ApplicationDefinition, ProgramDefinition
from lumora.services.connections.adapters.redis import owned_redis
from lumora.services.identity.domain import Identity
from lumora.services.interactions.adapters.wire import root_key
from lumora.services.scheduling.programs import program_schedule_id
from plugins.human_review.elements.specification import (
    ELEMENT_SPECIFICATIONS as REVIEW_SPECIFICATIONS,
)

ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def ui_node(request):
    if not request.config.getoption("--ui-clients"):
        pytest.skip("Select --ui-clients for actual TypeScript client integration")
    node = shutil.which("node")
    if node is None or not (ROOT / "ui/node_modules/vite").exists():
        pytest.fail(
            "UI client tests require Node and ui/pnpm install --frozen-lockfile", pytrace=False
        )
    return node


@pytest.fixture
def ui_mongo(ui_node):
    if not os.environ.get("LUMORA_TEST_MONGO_URI"):
        pytest.fail("UI API clients require an isolated LUMORA_TEST_MONGO_URI", pytrace=False)


async def test_graph_references_and_session_output_contracts(ui_node):
    output = await run_contracts(ui_node, "contracts")
    assert "UI graph and session output contracts passed" in output


async def test_schedule_consent_typescript_client_uses_private_authority(
    ui_node, ui_mongo, application, mongo_database, redis_uri, tmp_path
):
    endpoint = os.environ.get("LUMORA_TEST_TEMPORAL_ENDPOINT")
    if not endpoint:
        pytest.skip("Select the dedicated Temporal endpoint for native schedule clients")
    for specification in REVIEW_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    host = TemporalHostConfig(endpoint=endpoint, task_queue="lumora-consent-client-" + uuid4().hex)
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path, host=host) as api:
        native = await Client.connect(endpoint, namespace=host.namespace)
        deployment = CalendarDeployment(
            api.settings,
            WorkerSettings.model_validate(api.settings.model_dump(mode="python")),
            native,
        )
        reference = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="client-recurring-review",
                name="Client recurring review",
                owner=api.owner,
                implementation=review_definition(application.elements),
            ),
            headers=api.human,
        )
        key = uuid4().hex
        # The helper owns cleanup even if the client fails after calendar creation.
        deployment.schedule_ids.append(program_schedule_id(api.owner, key))
        try:
            output = await run_contracts(
                ui_node,
                "consent",
                {
                    **os.environ,
                    "LUMORA_TEST_UI_API_URL": str(api.http.base_url).rstrip("/") + "/api",
                    "LUMORA_TEST_UI_HUMAN_COOKIE": api.human["Cookie"],
                    "LUMORA_TEST_UI_PROGRAM_REFERENCE": reference.model_dump_json(),
                    "LUMORA_TEST_UI_SCHEDULE_KEY": key,
                },
            )
            assert "Schedule consent clients passed against native FastAPI" in output
            assert await mongo_database.workflow_consents.count_documents({}) == 1
            assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        finally:
            await deployment.close_schedules()


async def test_program_event_typescript_clients_use_canonical_execution(
    ui_node, ui_mongo, mongo_database, redis_uri, tmp_path
):
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        reference = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="client-event",
                name="Client event",
                owner=api.owner,
                implementation=ApplicationDefinition(implementation="greeting", version="1"),
            ),
            headers=api.human,
        )
        output = await run_contracts(
            ui_node,
            "events",
            {
                **os.environ,
                "LUMORA_TEST_UI_API_URL": str(api.http.base_url).rstrip("/") + "/api",
                "LUMORA_TEST_UI_HUMAN_COOKIE": api.human["Cookie"],
                "LUMORA_TEST_UI_PROGRAM_REFERENCE": reference.model_dump_json(),
            },
        )
        assert "Program event clients passed against native FastAPI" in output
        assert await mongo_database.program_event_sources.count_documents({"revoked": True}) == 1
        assert await mongo_database.workflow_credential_material.count_documents({}) == 0
        assert await mongo_database.program_executions.count_documents({}) == 1


@pytest.mark.parametrize("session", [False, True])
async def test_workflow_access_typescript_clients_use_native_admission(
    ui_node, ui_mongo, application, mongo_database, redis_uri, tmp_path, session
):
    for specification in REVIEW_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    async with managed_access_api(mongo_database.name, redis_uri, tmp_path) as api:
        reference = await publish_program(
            api.http,
            ProgramDefinition(
                program_id="client-managed-review",
                name="Client managed review",
                owner=api.owner,
                implementation=review_definition(application.elements),
            ),
            headers=api.human,
        )
        environment = {
            **os.environ,
            "LUMORA_TEST_UI_API_URL": str(api.http.base_url).rstrip("/") + "/api",
            "LUMORA_TEST_UI_HUMAN_COOKIE": api.human["Cookie"],
            "LUMORA_TEST_UI_REVIEW_COOKIE": api.reviewer["Cookie"],
            "LUMORA_TEST_UI_PROGRAM_REFERENCE": reference.model_dump_json(),
            "LUMORA_TEST_UI_PROGRAM_SESSION": "",
        }
        if session:
            created = await api.http.post(
                "/api/sessions",
                headers=api.human,
                json={"program": reference.model_dump(mode="json")},
            )
            assert created.status_code == 201, created.text
            environment["LUMORA_TEST_UI_PROGRAM_SESSION"] = created.json()["run_id"]
        output = await run_contracts(ui_node, "access", environment)
        assert "Workflow access clients passed against native FastAPI" in output
        assert await mongo_database.workflow_credential_material.count_documents({}) == 1
        async with asyncio.timeout(10):
            while await mongo_database.workflow_credential_material.count_documents(
                {"$or": [{"retired": False}, {"cleanup_pending": True}]}
            ):
                await asyncio.sleep(0.05)
        assert not list((tmp_path / "managed-workflow-access").rglob("*.json"))


async def test_human_review_typescript_clients_resume_a_native_workflow(
    ui_node, ui_mongo, application, mongo_database, redis_uri, tmp_path
):
    for specification in REVIEW_SPECIFICATIONS:
        application.elements.register_spec_class(specification)
    async with review_api(
        Identity.user("review-owner"),
        mongo_database.name,
        redis_uri,
        tmp_path,
        managed_delivery=True,
    ) as api:
        review = await api.publish("review", review_definition(application.elements))
        workflow = await api.publish("workflow", review_graph(review.reference))
        started = await api.http.post(
            "/api/executions",
            headers=api.human,
            json={
                "execution_id": api.root,
                "program": workflow.reference.model_dump(mode="json"),
                "inputs": {"subject": "ui-candidate"},
            },
        )
        assert started.status_code == 202, started.text
        await api.pending()
        output = await run_contracts(
            ui_node,
            "reviews",
            {
                **os.environ,
                "LUMORA_TEST_UI_API_URL": str(api.http.base_url).rstrip("/") + "/api",
                "LUMORA_TEST_UI_REVIEW_COOKIE": api.reviewer["Cookie"],
                "LUMORA_TEST_UI_HUMAN_COOKIE": api.human["Cookie"],
            },
        )
        assert "Human Review clients passed against native FastAPI" in output
        result = await api.http.get(f"/api/executions/{api.root}/result", headers=api.human)
        assert result.status_code == 200 and result.json()["phase"] == "completed", result.text
        assert result.json()["result"]["result"]["review"]["response"]["decision"] == "reject"


@pytest.mark.parametrize("suite", ["api", "blueprints", "sessions", "shares", "programs"])
async def test_existing_typescript_editor_clients_use_native_services(
    ui_node, ui_mongo, secret_settings, mongo_database, tmp_path, suite
):
    settings = secret_settings.model_copy(update={"library": True})
    if suite == "programs":
        settings = settings.model_copy(
            update={
                "element_modules": (
                    "support.elements",
                    "support.conditions",
                    "support.draft_configuration",
                    "support.value_operations",
                    "plugins.codex.specification",
                ),
                "application_modules": (
                    "support.programs",
                    "support.draft_configuration",
                    "support.typed_programs",
                ),
                "work_limits": WorkLimits(),
                "execution_profiles": {
                    **settings.execution_profiles,
                    "admin-only": K8sRunnerConfig(image="private-registry/privileged"),
                },
                "profile_access": ProfileAccessPolicy(
                    owners=(
                        OwnerProfileRule(
                            owner=Identity.user("owner"),
                            grant=ProfileGrant(
                                profiles=("thread", "process"), default_profile="thread"
                            ),
                        ),
                    )
                ),
            }
        )
    if suite == "shares":
        for invite in (
            invitation(
                "ui-received",
                sender_identity=Identity.user("sender", "Fixture sender"),
                recipient_identity=Identity.user("owner"),
            ),
            invitation("ui-sent", sender_identity=Identity.user("owner")),
            invitation("ui-foreign"),
        ):
            await mongo_database.shares.insert_one(invite.model_dump(mode="json"))
    redis_uri = os.environ.get("LUMORA_TEST_REDIS_URI")
    if suite == "sessions":
        if not redis_uri:
            pytest.fail(
                "UI session streams require an isolated LUMORA_TEST_REDIS_URI", pytrace=False
            )
        settings = settings.model_copy(
            update={
                "interactions": InteractionBackend.REDIS,
                "redis_uri": SecretStr(redis_uri),
                "element_modules": ("support.elements",),
            }
        )
    try:
        async with api_process(settings, tmp_path / "api.log") as http:
            environment = {
                **os.environ,
                "LUMORA_TEST_UI_API_URL": str(http.base_url).rstrip("/") + "/api",
            }
            output = await run_contracts(ui_node, suite, environment)
            assert "clients passed against native FastAPI" in output
    finally:
        if suite == "sessions" and redis_uri:
            async with owned_redis(redis_uri, decode_responses=True) as redis:
                async for execution in mongo_database.program_executions.find({}, {"_id": 1}):
                    keys = [
                        key
                        async for key in redis.scan_iter(match=root_key(execution["_id"]) + ":*")
                    ]
                    if keys:
                        await await_owned(redis.delete(*keys))
