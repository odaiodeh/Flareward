"""Explicitly opt-in actual-App journey using the shared live feature composition."""

import argparse
import asyncio
from importlib import import_module
from pathlib import Path
from urllib.parse import quote

from support.feature_browser_session import feature_browser_session
from support.live_coding import live_coding_credential
from support.live_feature import LiveFeature, live_feature


async def release_after_completion(deployment: LiveFeature, marker: Path) -> None:
    while not await asyncio.to_thread(marker.exists):
        await asyncio.sleep(0.2)
    root = (await asyncio.to_thread(marker.read_text)).strip()
    if not root or len(root) > 128:
        raise ValueError("Compute release requires the completed owned execution identity")
    response = await deployment.api.http.get(
        "/api/executions/" + quote(root, safe=""), headers=deployment.api.human
    )
    response.raise_for_status()
    record = response.json()
    if (
        record["program"] != deployment.programs.feature.model_dump(mode="json")
        or record["context"]["root_execution_id"] != root
        or record["phase"] not in {"completed", "failed", "cancelled"}
    ):
        raise ValueError("Compute release requires a terminal owned feature execution")
    await deployment.release_compute()
    print(
        "Owned compute removed; the authenticated API and artifacts remain available.", flush=True
    )


async def serve(assets: Path, directory: Path, backend_name: str) -> None:
    key = live_coding_credential()
    module = import_module(
        "support."
        + {"openshell": "openshell_deployment", "k8s": "kubernetes_deployment"}[backend_name]
    )
    async with (
        feature_browser_session(assets, directory) as browser,
        module.backend() as backend,
        live_feature(
            backend,
            key,
            browser.owner,
            browser.database,
            browser.redis_uri,
            directory,
            factory="support.feature_browser:create_app",
            environment=browser.environment,
            review_timeout_seconds=600,
        ) as deployment,
    ):
        await browser.show_login(deployment.api)
        print(
            "Live Codex enabled. Open Feature revision 1; invocation requires UI consent.",
            flush=True,
        )
        print(
            "After completion, write its execution ID to " + str(directory / "release-compute"),
            flush=True,
        )
        await release_after_completion(deployment, directory / "release-compute")
        await asyncio.Event().wait()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--assets", type=Path, required=True)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--backend", choices=("openshell", "k8s"), required=True)
    parser.add_argument("--live-coding", action="store_true")
    arguments = parser.parse_args()
    if not arguments.live_coding:
        parser.error("Explicit --live-coding authorization is required")
    try:
        asyncio.run(serve(arguments.assets, arguments.directory, arguments.backend))
    except KeyboardInterrupt:
        pass
