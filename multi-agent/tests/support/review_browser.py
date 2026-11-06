"""Run the actual App review screen against signed sessions, Mongo and a native workflow."""

import argparse
import asyncio
import os
from pathlib import Path
from uuid import uuid4

from fastapi.responses import FileResponse, RedirectResponse
from mas.core.async_work import await_owned
from mas.core.identity import Identity
from pymongo import AsyncMongoClient

from bootstrap.elements import installed_elements
from support.review_api import review_api, review_settings
from support.review_programs import review_definition, review_graph
from support.server import api_process
from support.workspace_browser import create_app as workspace_app


def create_app():
    app = workspace_app()

    @app.get("/fixture/reviews-login")
    async def login():
        response = RedirectResponse("/reviews")
        cookie = Path(os.environ["REVIEW_BROWSER_COOKIE_FILE"]).read_text()
        response.set_cookie("session", cookie, httponly=True, samesite="strict")
        return response

    @app.get("/fixture/reviews-owner-login")
    async def owner_login():
        directory = Path(os.environ["REVIEW_BROWSER_COOKIE_FILE"]).parent
        response = RedirectResponse("/executions/" + (directory / "root-execution").read_text())
        response.set_cookie(
            "session", (directory / "owner-cookie").read_text(), httponly=True, samesite="strict"
        )
        return response

    @app.get("/reviews")
    @app.get("/reviews/{review_id}")
    async def reviews():
        return FileResponse(Path(os.environ["PLACEMENT_BROWSER_ASSETS"]) / "workspace-browser.html")

    return app


async def serve(assets: Path, directory: Path) -> None:
    directory.mkdir(parents=True, exist_ok=True)
    database = "unifai_review_browser_" + uuid4().hex
    owner = Identity.user("review-owner")
    settings = review_settings(owner, database, os.environ["UNIFAI_TEST_REDIS_URI"])
    os.environ["PLACEMENT_BROWSER_ASSETS"] = str(assets.resolve())
    os.environ["BROWSER_TEAM_PREFIX"] = "review-" + uuid4().hex
    os.environ["REVIEW_BROWSER_COOKIE_FILE"] = str(directory / "reviewer-cookie")
    mongo = AsyncMongoClient(os.environ["UNIFAI_TEST_MONGO_URI"])
    try:
        async with api_process(
            settings,
            directory / "identity.log",
            factory="support.browser_identity:create_app",
            health_path="/health",
        ) as identity:
            settings = settings.model_copy(
                update={
                    "identity_url": str(identity.base_url).rstrip("/"),
                    "library": True,
                    "admin_config_database": database,
                }
            )
            async with review_api(
                owner,
                database,
                os.environ["UNIFAI_TEST_REDIS_URI"],
                directory,
                factory="support.review_browser:create_app",
                settings=settings,
            ) as api:
                # This test-only login route sets the actual assigned reviewer's signed cookie.
                # Read at request time by the child process through a private fixture file.
                for name, value in (
                    ("reviewer-cookie", api.reviewer["Cookie"].removeprefix("session=")),
                    ("owner-cookie", api.human["Cookie"].removeprefix("session=")),
                    ("root-execution", api.root),
                ):
                    descriptor = os.open(
                        directory / name, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
                    )
                    with os.fdopen(descriptor, "w") as destination:
                        destination.write(value)
                definition = review_definition(installed_elements(settings.element_modules))
                definition.config["template"]["timeout_seconds"] = 600
                definition.config["reconcile_seconds"] = 5
                review = await api.publish("browser-review", definition)
                workflow = await api.publish("browser-workflow", review_graph(review.reference))
                started = await api.http.post(
                    "/api/executions",
                    headers=api.human,
                    json={
                        "execution_id": api.root,
                        "program": workflow.reference.model_dump(mode="json"),
                        "inputs": {
                            "subject": {
                                "candidate": "browser-exact-candidate",
                                "checks": ["tests passed", "analysis passed"],
                            }
                        },
                    },
                )
                assert started.status_code == 202, started.text
                pending = await api.pending()
                print(str(api.http.base_url).rstrip("/") + "/fixture/reviews-login", flush=True)
                print(
                    str(api.http.base_url).rstrip("/") + "/fixture/reviews-owner-login", flush=True
                )
                print("Review occurrence " + pending.review_id, flush=True)
                while True:
                    result = await api.http.get(f"/api/executions/{api.root}", headers=api.human)
                    if result.json()["phase"] in ("completed", "failed", "cancelled"):
                        print("Workflow outcome: " + result.text, flush=True)
                        break
                    await asyncio.sleep(1)
                await asyncio.Event().wait()
    finally:
        for name in (
            "PLACEMENT_BROWSER_ASSETS",
            "BROWSER_TEAM_PREFIX",
            "REVIEW_BROWSER_COOKIE_FILE",
        ):
            os.environ.pop(name, None)
        await await_owned(mongo.drop_database(database))
        await await_owned(mongo.close())
        for name in ("reviewer-cookie", "owner-cookie", "root-execution"):
            (directory / name).unlink(missing_ok=True)
        print("Removed review browser fixture " + database, flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    options = parser.parse_args()
    try:
        asyncio.run(serve(options.assets, options.directory))
    except KeyboardInterrupt:
        pass
