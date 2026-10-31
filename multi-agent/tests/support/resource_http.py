"""Shared public resource-authoring contract for blueprint/session scenarios."""

import httpx


async def create_resource(
    http: httpx.AsyncClient,
    category: str,
    type_key: str,
    name: str,
    config: dict,
    **metadata,
) -> str:
    response = await http.post(
        "/api/resources",
        json={"category": category, "type": type_key, "name": name, "config": config, **metadata},
    )
    assert response.status_code == 201, response.text
    return response.json()["rid"]
