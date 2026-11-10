"""Author saved coding dependencies and capture protected bundles through native APIs."""

import httpx
import pytest
from pydantic import SecretStr

from lumora.executions.domain.preferences import ExecutionSelection
from lumora.resources.domain.bundles import ElementBundle
from plugins.adlc.programs.coding import CodingFileCandidateConfig
from plugins.codex.config import CodexConfig


class CodingResourceLibrary:
    def __init__(self, http: httpx.AsyncClient, human: dict[str, str]) -> None:
        self._http, self._human = http, human

    async def create(self, category, type_key, configuration, *, execution_profile=None, name=None):
        response = await self._http.post(
            "/api/resources",
            headers=self._human,
            json={
                "category": category,
                "type": type_key,
                "name": name or type_key,
                "config": configuration,
                "execution": {"profile": execution_profile} if execution_profile else {},
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    async def capture(self, resource, *, private: SecretStr | None = None) -> ElementBundle:
        response = await self._http.post(
            "/api/resources/snapshot", headers=self._human, json={"source": resource["source"]}
        )
        assert response.status_code == 200, response.text
        if private is not None and private.get_secret_value() in response.text:
            pytest.fail("Private coding credential appeared in a resource snapshot", pytrace=False)
        return ElementBundle.model_validate(response.json())

    async def coding(
        self, config: CodexConfig, profile: str, *, name: str = "codex_coding"
    ) -> ElementBundle:
        preparation = await self.create("providers", "inline_workspace", {}, name=name + " inputs")
        configuration = {
            **config.model_dump(mode="json", exclude={"api_key", "workspace_preparation"}),
            "workspace_preparation": "$ref:" + preparation["rid"],
        }
        if config.api_key is not None:
            configuration["api_key"] = config.api_key.get_secret_value()
        coder = await self.create(
            "operations", "codex_coding", configuration, execution_profile=profile, name=name
        )
        return await self.capture(coder, private=config.api_key)


async def saved_coding_candidate(
    http: httpx.AsyncClient,
    human: dict[str, str],
    *,
    config: CodexConfig,
    profile: str,
    artifact_profile: str | None = None,
) -> CodingFileCandidateConfig:
    library = CodingResourceLibrary(http, human)
    storage_profile = artifact_profile or profile
    store = await library.create("providers", "artifact_store", {})
    coding = await library.coding(config, profile)
    publisher = await library.create(
        "operations",
        "publish_file_content",
        {
            "store": "$ref:" + store["rid"],
            "namespace": "engineering",
        },
        execution_profile=storage_profile,
    )
    loader = await library.create(
        "operations",
        "load_artifact_content",
        {"store": "$ref:" + store["rid"]},
        execution_profile=storage_profile,
    )
    reader = await library.create(
        "operations", "read_workspace_content", {}, execution_profile=profile
    )
    publication = await library.capture(publisher)
    assert len(coding.entries) == 2 and len(publication.entries) == 2
    return CodingFileCandidateConfig(
        coding=coding,
        loader=await library.capture(loader),
        reader=await library.capture(reader),
        publisher=publication,
        path="answer.py",
        execution=ExecutionSelection(profile=profile),
        artifact_execution=ExecutionSelection(profile=storage_profile),
    )
