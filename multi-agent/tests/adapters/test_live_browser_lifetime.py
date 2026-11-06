"""The owned browser fixture cannot release compute for active or unrelated work."""

from unittest.mock import create_autospec

import httpx
import pytest
from mas.domain.programs.models import ProgramRef
from support.engineering_api import EngineeringAPI
from support.feature_api import FeaturePrograms
from support.live_feature import LiveFeature
from support.live_feature_browser import release_after_completion


@pytest.mark.parametrize("case", ["completed", "running", "foreign-program", "child", "denied"])
async def test_compute_release_requires_owned_terminal_feature(tmp_path, case):
    reference = ProgramRef(program_id="feature", revision=1)
    record = {
        "program": reference.model_dump(mode="json"),
        "phase": "completed",
        "context": {"root_execution_id": "root"},
    }
    if case == "running":
        record["phase"] = "running"
    elif case == "foreign-program":
        record["program"]["program_id"] = "other"
    elif case == "child":
        record["context"]["root_execution_id"] = "parent"

    def respond(request):
        assert request.url.path == "/api/executions/root"
        assert request.headers["Cookie"] == "session=fixture"
        return httpx.Response(403 if case == "denied" else 200, json=record)

    async with httpx.AsyncClient(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(respond)
    ) as http:
        deployment = create_autospec(LiveFeature, instance=True)
        deployment.api = EngineeringAPI(
            http, {"Cookie": "session=fixture"}, {}, tmp_path / "workspace", tmp_path / "api.log"
        )
        deployment.programs = FeaturePrograms(reference, reference, reference)
        marker = tmp_path / "release-compute"
        marker.write_text("root")
        if case == "completed":
            await release_after_completion(deployment, marker)
            deployment.release_compute.assert_awaited_once()
        else:
            with pytest.raises(httpx.HTTPStatusError if case == "denied" else ValueError):
                await release_after_completion(deployment, marker)
            deployment.release_compute.assert_not_awaited()
