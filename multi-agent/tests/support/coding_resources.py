"""Author saved coding dependencies and capture protected bundles through native APIs."""

import httpx
import pytest
from mas.domain.element_bundles import ElementBundle
from mas.domain.execution_preferences import ExecutionSelection
from mas_plugins.coding.codex.config import CodexConfig
from mas_plugins.engineering.coding import CodingFileCandidateConfig


async def saved_coding_candidate(
    http: httpx.AsyncClient,
    human: dict[str, str],
    *,
    config: CodexConfig,
    profile: str,
    artifact_profile: str | None = None,
) -> CodingFileCandidateConfig:
    storage_profile = artifact_profile or profile

    async def create(category, type_key, configuration, *, execution_profile=None):
        response = await http.post(
            "/api/resources",
            headers=human,
            json={
                "category": category,
                "type": type_key,
                "name": type_key,
                "config": configuration,
                "execution": {"profile": execution_profile} if execution_profile else {},
            },
        )
        assert response.status_code == 201, response.text
        return response.json()

    store = await create("providers", "artifact_store", {})
    preparation = await create("providers", "inline_workspace", {})
    configuration = {
        **config.model_dump(mode="json", exclude={"api_key", "workspace_preparation"}),
        "workspace_preparation": "$ref:" + preparation["rid"],
    }
    if config.api_key is not None:
        configuration["api_key"] = config.api_key.get_secret_value()
    coder = await create(
        "operations",
        "codex_coding",
        configuration,
        execution_profile=profile,
    )
    publisher = await create(
        "operations",
        "publish_file_content",
        {
            "store": "$ref:" + store["rid"],
            "namespace": "engineering",
        },
        execution_profile=storage_profile,
    )
    loader = await create(
        "operations",
        "load_artifact_content",
        {"store": "$ref:" + store["rid"]},
        execution_profile=storage_profile,
    )
    reader = await create("operations", "read_workspace_content", {}, execution_profile=profile)

    async def snapshot(resource):
        response = await http.post(
            "/api/resources/snapshot", headers=human, json={"source": resource["source"]}
        )
        assert response.status_code == 200, response.text
        if config.api_key is not None and config.api_key.get_secret_value() in response.text:
            pytest.fail("Private coding credential appeared in a resource snapshot", pytrace=False)
        return ElementBundle.model_validate(response.json())

    coding, publication = await snapshot(coder), await snapshot(publisher)
    assert len(coding.entries) == 2 and len(publication.entries) == 2
    return CodingFileCandidateConfig(
        coding=coding,
        loader=await snapshot(loader),
        reader=await snapshot(reader),
        publisher=publication,
        path="answer.py",
        execution=ExecutionSelection(profile=profile),
        artifact_execution=ExecutionSelection(profile=storage_profile),
    )
