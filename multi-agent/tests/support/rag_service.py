"""Owned RAG authoring protocol fixture with real HTTP identity checks."""

from fastapi import FastAPI, HTTPException, Request


def create_app():
    app = FastAPI()

    @app.get("/api/health/")
    async def health():
        return {"status": "ok", "message": "Fixture ready"}

    @app.get("/api/docs/available.tags.get")
    async def tags(request: Request):
        if request.headers.get("X-Authenticated-User") != "owner":
            raise HTTPException(status_code=403)
        assert request.query_params["limit"] == "3"
        return {"options": [{"label": "Shared tag", "value": "tag"}], "total": 1}

    @app.get("/api/docs/available.docs.get")
    async def documents(request: Request):
        if request.headers.get("X-Authenticated-User") != "owner":
            raise HTTPException(status_code=403)
        assert request.query_params["search_regex"] == "selected"
        return {"documents": [{"name": "Selected document", "id": "doc"}], "total": 1}

    return app
