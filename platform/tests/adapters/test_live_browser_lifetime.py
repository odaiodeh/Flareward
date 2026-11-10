"""The owned browser fixture cannot release compute for active or unrelated work."""

from unittest.mock import create_autospec

import httpx
import pytest
from support.engineering_api import EngineeringAPI
from support.live_feature import LiveFeature
from support.live_feature_browser import release_after_completion

from lumora.programs.domain.models import ProgramRef


@pytest.mark.parametrize(
    "case",
    ["completed", "authored", "running", "other-program", "child", "denied", "revision-denied"],
)
async def test_compute_release_requires_owned_terminal_feature(tmp_path, case):
    reference = ProgramRef(program_id="feature", revision=1)
    record = {
        "program": reference.model_dump(mode="json"),
        "phase": "completed",
        "context": {"root_execution_id": "root"},
    }
    if case == "running":
        record["phase"] = "running"
    elif case == "authored":
        record["program"]["program_id"] = "authored-feature"
    elif case == "child":
        record["context"]["root_execution_id"] = "parent"

    def respond(request):
        assert request.headers["Cookie"] == "session=fixture"
        if request.url.path == "/api/executions/root":
            return httpx.Response(403 if case == "denied" else 200, json=record)
        assert (
            request.url.path == "/api/programs/" + record["program"]["program_id"] + "/revisions/1"
        )
        return httpx.Response(
            403 if case == "revision-denied" else 200,
            json={
                "definition": {
                    "implementation": {
                        "kind": "application",
                        "implementation": "other" if case == "other-program" else "coding_feature",
                        "version": "1",
                    }
                }
            },
        )

    async with httpx.AsyncClient(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(respond)
    ) as http:
        deployment = create_autospec(LiveFeature, instance=True)
        deployment.api = EngineeringAPI(
            http, {"Cookie": "session=fixture"}, {}, tmp_path / "workspace", tmp_path / "api.log"
        )
        marker = tmp_path / "release-compute"
        marker.write_text("root")
        if case in {"completed", "authored"}:
            await release_after_completion(deployment, marker)
            deployment.release_compute.assert_awaited_once()
        else:
            with pytest.raises(
                httpx.HTTPStatusError if case in {"denied", "revision-denied"} else ValueError
            ):
                await release_after_completion(deployment, marker)
            deployment.release_compute.assert_not_awaited()
