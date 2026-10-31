"""Separately running native API and actual provider protocol services, without paid calls."""

from pydantic import AnyHttpUrl
from support.server import api_process


async def test_native_actions_use_real_mcp_and_rag_http_services(secret_settings, tmp_path):
    async with api_process(
        secret_settings,
        tmp_path / "mcp.log",
        factory="support.mcp_service:create_app",
        health_path="/health",
    ) as mcp:
        async with api_process(
            secret_settings,
            tmp_path / "rag.log",
            factory="support.rag_service:create_app",
            health_path="/api/health/",
        ) as rag:
            settings = secret_settings.model_copy(
                update={"rag_base_url": AnyHttpUrl(str(rag.base_url))}
            )
            async with api_process(settings, tmp_path / "api.log") as api:
                results = {}
                for uid, arguments in (
                    ("mcp.get_tools_names", {"mcp_url": str(mcp.base_url).rstrip("/") + "/mcp"}),
                    (
                        "mcp.validate_connection",
                        {"mcp_url": str(mcp.base_url).rstrip("/") + "/mcp"},
                    ),
                    ("rag.get_available_tags", {"limit": 3, "user_id": "forged"}),
                    ("rag.get_available_docs", {"search_regex": "selected", "user_id": "forged"}),
                    ("rag.validate_connection", {"base_url": str(rag.base_url)}),
                ):
                    response = await api.post(
                        "/api/actions/action.execute", json={"uid": uid, "inputData": arguments}
                    )
                    assert response.status_code == 200 and response.json()["success"], response.text
                    results[uid] = response.json()
                assert set(results["mcp.get_tools_names"]["tool_names"]) == {
                    "read_remote_evidence",
                    "read_failure",
                }
                assert results["mcp.validate_connection"]["is_reachable"]
                assert results["rag.get_available_tags"]["tags"] == ["Shared tag"]
                assert results["rag.get_available_docs"]["documents"] == [
                    {"name": "Selected document", "id": "doc"}
                ]
                assert results["rag.validate_connection"]["is_reachable"]
