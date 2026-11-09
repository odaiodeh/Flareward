"""Actual App workspace routes; only external identity/settings services are fixtures."""

import asyncio
import os
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse

from flareward.api.dependencies import authenticated
from flareward.services.identity.domain import Identity
from support.placement_browser import create_app as placement_app


def create_app():
    return add_workspace_routes(placement_app())


def add_workspace_routes(app: FastAPI) -> FastAPI:

    @app.middleware("http")
    async def delayed_selection(request: Request, call_next):
        if request.url.path == "/api/shares/shares.list" and request.query_params.get(
            "teamId", ""
        ).endswith("-alpha"):
            response = await call_next(request)
            await asyncio.sleep(2)
            return response
        # Delay actual native responses so switching types/editors exercises stale completion.
        if (
            (
                request.url.path == "/api/catalog/element.spec.get"
                and request.query_params.get("type") == "mock_agent_node"
            )
            or (
                request.url.path == "/api/resources/resources.list"
                and request.query_params.get("category") == "nodes"
            )
            or request.url.path == "/api/collaboration/edit_lock.acquire"
        ):
            await asyncio.sleep(2)
        return await call_next(request)

    @app.get("/fixture/auth/user/groups")
    async def groups(caller: Annotated[Identity, Depends(authenticated)]):
        return {"groups": []}

    @app.get("/fixture/teams/teams.list")
    async def memberships(caller: Annotated[Identity, Depends(authenticated)]):
        async with httpx.AsyncClient() as upstream:
            response = await upstream.get(
                os.environ["FLAREWARD_IDENTITY_URL"] + "/api/teams/teams.list",
                params={"userId": caller.id},
            )
            response.raise_for_status()
            return response.json()

    @app.get("/inventory")
    @app.get("/agentic-ai")
    @app.get("/executions/{execution_id}")
    async def workspace():
        return FileResponse(Path(os.environ["PLACEMENT_BROWSER_ASSETS"]) / "workspace-browser.html")

    return app
