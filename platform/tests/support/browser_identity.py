"""Synthetic upstream membership service for the owned workspace browser fixture."""

import os
from typing import Annotated

from fastapi import FastAPI, Query


def teams() -> list[dict]:
    prefix = os.environ["BROWSER_TEAM_PREFIX"]
    return [
        {
            "team_id": f"{prefix}-{suffix}",
            "name": f"Platform {suffix.title()}",
            "created_by": "browser-owner",
            "members": [{"type": "user", "id": "browser-owner", "display_name": "Owner"}],
            "created_at": "2026-10-30T00:00:00Z",
            "updated_at": "2026-10-30T00:00:00Z",
            "effective_member_count": 1,
        }
        for suffix in ("alpha", "beta")
    ]


def create_app() -> FastAPI:
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"ok": True}

    @app.get("/api/teams/teams.list")
    async def memberships(user_id: Annotated[str, Query(alias="userId")]):
        return {"teams": teams() if user_id == "browser-owner" else []}

    return app
