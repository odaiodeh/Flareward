"""Actual UI/managed feature flow with controlled design/CLI and production checks."""

import argparse
import asyncio
import os
from pathlib import Path

from fastapi.responses import FileResponse, RedirectResponse
from pydantic import SecretStr

from lumora.bootstrap.asgi import create_app as platform_app
from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.programs.domain.models import ApplicationDefinition, ProgramBody
from lumora.services.identity.domain import Identity
from lumora.services.verification.domain.models import CheckRequirement
from plugins.adlc.programs.coding import CodingFileWork
from plugins.adlc.programs.program import EngineeringCandidate
from plugins.artifacts.elements.specification import ELEMENT_SPECIFICATIONS as ARTIFACTS
from plugins.codex.config import CodexConfig
from plugins.codex.specification import CodexSpec
from plugins.human_review.elements.specification import ELEMENT_SPECIFICATIONS as REVIEWS
from plugins.verification.elements.specification import ELEMENT_SPECIFICATIONS as CHECKS
from support.check_program_publication import CheckProgramSetup
from support.coding_cli import write_codex_cli
from support.coding_resources import CodingResourceLibrary, saved_coding_candidate
from support.engineering_api import engineering_api, policies
from support.feature_api import publish_feature
from support.feature_browser_session import feature_browser_session
from support.placement_browser import add_browser_routes
from support.python_checks import python_verifier_definition
from support.workspace_browser import add_workspace_routes


def create_app():
    app = add_workspace_routes(add_browser_routes(platform_app()))

    @app.get("/fixture/feature-login")
    async def login():
        cookie = await asyncio.to_thread(Path(os.environ["FEATURE_BROWSER_COOKIE_FILE"]).read_text)
        response = RedirectResponse("/programs")
        response.set_cookie("session", cookie, httponly=True, samesite="strict")
        return response

    @app.get("/programs")
    async def programs():
        return FileResponse(Path(os.environ["PLACEMENT_BROWSER_ASSETS"]) / "workspace-browser.html")

    return app


async def serve(assets: Path, directory: Path) -> None:
    async with feature_browser_session(assets, directory) as browser:
        executable = await asyncio.to_thread(write_codex_cli, directory)
        registry = ElementRegistry()
        for specification in (*ARTIFACTS, *REVIEWS, *CHECKS, CodexSpec):
            registry.register_spec_class(specification)
        policy = policies(browser.owner)[0].model_copy(
            update={
                "requirements": (
                    CheckRequirement(
                        check="tests@1", verifiers=frozenset({"program-ci"}), requires_reports=True
                    ),
                )
            }
        )
        async with engineering_api(
            browser.owner,
            browser.database,
            browser.redis_uri,
            directory,
            application_modules=(
                "plugins.adlc.programs.design",
                "plugins.adlc.programs.feature",
                "plugins.adlc.programs.coding",
                "plugins.adlc.programs.designer",
                "support.feature_design",
                "plugins.testing.programs.python_check",
            ),
            element_modules=(
                "plugins.codex.specification",
                "plugins.testing.specification",
            ),
            library=True,
            factory="support.feature_browser:create_app",
            verification_policies={"engineering@1": policy},
            check_programs={
                "program@1": CheckProgramSetup(
                    python_verifier_definition(Identity.user("trusted-verifier"), "process"),
                    policies(browser.owner)[1].model_copy(update={"verifier": "program-ci"}),
                    input_artifact_max_bytes=65_536,
                )
            },
            environment={
                **browser.environment,
                "PATH": str(executable.parent) + os.pathsep + os.environ.get("PATH", ""),
                "LUMORA_PYTHON_CHECK_EXECUTION_ENABLED": "true",
                "LUMORA_PYTHON_CHECK_DIRECTORY": str(directory / "check-workspaces"),
            },
        ) as api:
            config = await saved_coding_candidate(
                api.http,
                api.human,
                config=CodexConfig(
                    model="engineering-fixture", api_key=SecretStr("private-test-token")
                ),
                profile="process",
            )
            await CodingResourceLibrary(api.http, api.human).coding(
                CodexConfig(model="designer-fixture", api_key=SecretStr("private-test-token")),
                "process",
                name="Design coding agent",
            )
            body = ProgramBody(
                implementation=ApplicationDefinition(
                    implementation="coding_file_candidate",
                    version="1",
                    config=config.model_dump(mode="json"),
                ),
                input_schema=CodingFileWork.model_json_schema(),
                output_schema=EngineeringCandidate.model_json_schema(),
            )
            await publish_feature(
                api.http,
                api.human,
                browser.owner,
                registry,
                body,
                "process",
                review_timeout_seconds=600,
                runners=("program@1",),
                requirements=policy.requirements,
            )
            await browser.show_login(api)
            print(
                "Controlled CLI fixture; no live model calls. Open Feature revision 1.", flush=True
            )
            await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    arguments = parser.parse_args()
    try:
        asyncio.run(serve(arguments.assets, arguments.directory))
    except KeyboardInterrupt:
        pass
