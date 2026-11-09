"""The production assembly path uses the server loop and owns its background work."""

import asyncio

import httpx
import pytest
from fastapi import HTTPException, Request
from pydantic import ValidationError
from runengine.adapters.coordination.config import LocalHostConfig, TemporalHostConfig
from runengine.invocation.config import K8sRunnerConfig, ThreadRunnerConfig
from support.elements import element_registry

from flareward.api.app import create_app
from flareward.api.dependencies import authenticated
from flareward.bootstrap.platform import compose_platform
from flareward.bootstrap.settings.platform_settings import (
    AuthenticationKind,
    PlatformSettings,
    StorageKind,
)
from flareward.programs.domain.models import ApplicationDefinition, ProgramDefinition
from flareward.services.identity.domain import Identity


def settings():
    return PlatformSettings(
        host=LocalHostConfig(),
        storage=StorageKind.MEMORY,
        interactions="disabled",
        authentication=AuthenticationKind.DEVELOPMENT,
        development_user="alice",
        application_modules=("support.programs",),
        reconcile_interval=0.05,
    )


async def test_profile_discovery_exposes_only_approved_names_and_requires_authentication():
    configured = settings().model_copy(
        update={
            "execution_profiles": {
                "isolated": K8sRunnerConfig(
                    image="private-registry/receiver:fixture",
                    env={"PROFILE_SENTINEL": "private-config-value"},
                ),
                "trusted-worker": ThreadRunnerConfig(),
            },
        }
    )
    app = create_app(
        services_factory=lambda: compose_platform(configured, elements=element_registry())
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as client:
            response = await client.get("/api/catalog/execution-profiles")
            assert response.status_code == 200
            assert response.json() == {
                "profiles": ["isolated", "trusted-worker"],
                "default_profile": "trusted-worker",
                "environment_profiles": ["isolated"],
            }
            assert "private-config-value" not in response.text

        async def denied(request: Request):
            raise HTTPException(status_code=401, detail="Sign in required")

        app.dependency_overrides[authenticated] = denied
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as client:
            assert (await client.get("/api/catalog/execution-profiles")).status_code == 401


async def test_lifespan_assembles_services_and_projects_results_without_reader():
    app = create_app(
        services_factory=lambda: compose_platform(settings(), elements=element_registry())
    )
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as client:
            definition = ProgramDefinition(
                program_id="lifecycle",
                name="Lifecycle",
                owner=Identity.user("alice"),
                implementation=ApplicationDefinition(implementation="greeting", version="1"),
            )
            assert (
                await client.put(
                    "/api/programs/lifecycle",
                    json={"definition": definition.model_dump(mode="json"), "expected_version": 0},
                )
            ).status_code == 200
            assert (
                await client.post("/api/programs/lifecycle/revisions", json={"expected_version": 1})
            ).status_code == 201
            submitted = await client.post(
                "/api/executions",
                json={
                    "program": {"program_id": "lifecycle", "revision": 1},
                    "inputs": {"name": "startup"},
                    "execution_id": "lifespan-run",
                },
            )
            assert submitted.status_code == 202
            async with asyncio.timeout(5):
                while True:
                    record = await app.state.platform.executions.get(
                        "lifespan-run", Identity.user("alice")
                    )
                    if record.phase.value == "completed":
                        break
                    await asyncio.sleep(0.01)
            assert record.result == {"answer": "hello startup"}
    assert app.state.platform is None


def test_production_configuration_requires_durable_records_and_explicit_authentication():
    with pytest.raises(ValidationError, match="durable application records"):
        PlatformSettings(
            host=TemporalHostConfig(),
            storage="memory",
            authentication="development",
            development_user="alice",
        )
    with pytest.raises(ValidationError, match="explicit|DEVELOPMENT_USER"):
        PlatformSettings(host=LocalHostConfig(), storage="memory", authentication="development")
