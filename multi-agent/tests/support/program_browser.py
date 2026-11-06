"""Actual App program composer with a pinned graph child and real signed-cookie API."""

import argparse
import asyncio
import os
from contextlib import AsyncExitStack
from pathlib import Path
from uuid import uuid4

from fastapi import Request
from fastapi.responses import FileResponse, RedirectResponse
from mas.core.async_work import await_owned
from mas.core.identity import Identity
from mas.domain.programs.models import ProgramDefinition
from outbound.redis_client import owned_redis
from pymongo import AsyncMongoClient

from support.condition_scenarios import routing_graph
from support.identity import authenticated_cookie
from support.library_resources import seed_condition_resource, seed_operation_resources
from support.native_settings import session_settings
from support.operations import operation_graph
from support.server import api_process
from support.workspace_browser import create_app as workspace_app


def create_app():
    app = workspace_app()

    @app.middleware("http")
    async def delayed_capture(request: Request, call_next):
        if request.url.path == "/api/resources/snapshot":
            await asyncio.sleep(2)
        return await call_next(request)

    @app.get("/fixture/programs-login")
    async def login():
        response = RedirectResponse("/programs")
        response.set_cookie(
            "session", os.environ["PROGRAM_BROWSER_COOKIE"], httponly=True, samesite="strict"
        )
        return response

    @app.get("/programs")
    async def programs():
        return FileResponse(Path(os.environ["PLACEMENT_BROWSER_ASSETS"]) / "workspace-browser.html")

    return app


async def serve(assets: Path, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    database = "unifai_program_browser_" + uuid4().hex
    owner = Identity.user("program-owner")
    redis_uri = os.environ["UNIFAI_TEST_REDIS_URI"]
    settings = session_settings(database, redis_uri).model_copy(
        update={
            "reviews_enabled": False,
            "review_policies": {},
            "application_modules": ("support.programs", "support.typed_programs"),
            "element_modules": ("support.elements", "support.conditions"),
            "library": True,
            "admin_config_database": database,
        }
    )
    os.environ["PLACEMENT_BROWSER_ASSETS"] = str(assets.resolve())
    os.environ["BROWSER_TEAM_PREFIX"] = "program-" + uuid4().hex
    mongo = AsyncMongoClient(os.environ["UNIFAI_TEST_MONGO_URI"])
    try:
        async with AsyncExitStack() as resources:
            identity = await resources.enter_async_context(
                api_process(
                    settings,
                    directory / "identity.log",
                    factory="support.browser_identity:create_app",
                    health_path="/health",
                )
            )
            settings = settings.model_copy(
                update={"identity_url": str(identity.base_url).rstrip("/")}
            )
            redis = await resources.enter_async_context(
                owned_redis(redis_uri, decode_responses=True)
            )
            cookie = await resources.enter_async_context(
                authenticated_cookie(
                    redis, owner.id, settings.secret_key.get_secret_value(), ttl=1800
                )
            )
            os.environ["PROGRAM_BROWSER_COOKIE"] = cookie
            http = await resources.enter_async_context(
                api_process(
                    settings, directory / "api.log", factory="support.program_browser:create_app"
                )
            )
            http.cookies.set("session", cookie)
            await seed_operation_resources(http, profile="process")
            await seed_condition_resource(http)
            graph = routing_graph("threshold", {"input_path": ["output"], "threshold": 0.5})
            graph = graph.model_copy(
                update={
                    "conditions": (),
                    "resources": tuple(
                        resource
                        for resource in graph.resources
                        if resource.key.category != "conditions"
                    ),
                }
            )
            route_draft = ProgramDefinition(
                program_id="browser-routing",
                name="Routing example",
                owner=owner,
                implementation=graph,
            )
            response = await http.put(
                "/api/programs/browser-routing",
                json={"definition": route_draft.model_dump(mode="json"), "expected_version": 0},
            )
            assert response.status_code == 200, response.text
            definition = ProgramDefinition(
                program_id="browser-map-body",
                name="Browser operation graph",
                owner=owner,
                implementation=operation_graph(),
            )
            saved = await http.put(
                "/api/programs/browser-map-body",
                json={"definition": definition.model_dump(mode="json"), "expected_version": 0},
            )
            assert saved.status_code == 200, saved.text
            published = await http.post(
                "/api/programs/browser-map-body/revisions", json={"expected_version": 1}
            )
            assert published.status_code == 201, published.text
            print(str(http.base_url).rstrip("/") + "/fixture/programs-login", flush=True)
            print("Pinned child: browser-map-body revision 1", flush=True)
            await asyncio.Event().wait()
    finally:
        for name in ("PLACEMENT_BROWSER_ASSETS", "BROWSER_TEAM_PREFIX", "PROGRAM_BROWSER_COOKIE"):
            os.environ.pop(name, None)
        await await_owned(mongo.drop_database(database))
        await await_owned(mongo.close())
        print("Removed program browser fixture " + database, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    options = parser.parse_args()
    try:
        asyncio.run(serve(options.assets, options.directory))
    except KeyboardInterrupt:
        pass
