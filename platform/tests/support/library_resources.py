"""Shared saved-resource setup through native APIs or explicit storage boundaries."""

from lumora.resources.domain.builtins import (
    BuiltinResourceDescriptor,
    BuiltinUserConfig,
    identity_to_key,
)
from lumora.resources.domain.models import Resource
from lumora.services.identity.domain import Identity


async def seed_operation_resources(http, *, profile="thread"):
    leaf = await http.post(
        "/api/resources",
        json={
            "category": "tools",
            "type": "platform_dependency",
            "name": "Saved leaf",
            "config": {},
        },
    )
    assert leaf.status_code == 201, leaf.text
    middle = await http.post(
        "/api/resources",
        json={
            "category": "tools",
            "type": "platform_dependency",
            "name": "Saved middle",
            "config": {"value": "saved-middle", "dependency": "$ref:" + leaf.json()["rid"]},
        },
    )
    assert middle.status_code == 201, middle.text
    operation = await http.post(
        "/api/resources",
        json={
            "category": "operations",
            "type": "platform_text_operation",
            "name": "Saved text operation",
            "config": {"dependency": "$ref:" + middle.json()["rid"]},
            "execution": {"profile": profile},
        },
    )
    assert operation.status_code == 201, operation.text
    return operation.json(), middle.json(), leaf.json()


async def seed_private_agent_resources(database, owner, cipher):
    agent = Resource(
        rid="library-agent",
        identity=owner,
        category="nodes",
        type="mock_agent_node",
        name="Existing agent",
        cfg_dict={"type": "mock_agent_node", "llm": "$ref:library-model"},
        nested_refs=["library-model"],
    )
    model = Resource(
        rid="library-model",
        identity=Identity.user("admin"),
        category="llms",
        type="mock",
        name="Existing model",
        cfg_dict={
            "type": "mock",
            "base_url": "http://unused.invalid",
            "api_key": cipher.encrypt("admin-private-default"),
        },
    )
    for resource in (agent, model):
        await database.resources.insert_one(
            {"_id": resource.rid, **resource.model_dump(mode="json")}
        )
    descriptor = BuiltinResourceDescriptor(rid=model.rid, visibility="public")
    await database.builtin_resource_descriptors.insert_one(
        {"_id": model.rid, **descriptor.model_dump(mode="json")}
    )
    overlay = BuiltinUserConfig(
        resource_id=model.rid,
        identity_key=identity_to_key(owner),
        fields={"api_key": cipher.encrypt("caller-private-value")},
    )
    await database.builtin_user_configs.insert_one(
        {"_id": overlay.config_id, **overlay.model_dump(mode="json")}
    )
    return agent, model


async def seed_condition_resource(http, *, profile="process"):
    response = await http.post(
        "/api/resources",
        json={
            "category": "conditions",
            "type": "threshold",
            "name": "Saved numeric threshold",
            "config": {"input_path": ["output"], "threshold": 0.5},
            "execution": {"profile": profile},
        },
    )
    assert response.status_code == 201, response.text
    return response.json()
