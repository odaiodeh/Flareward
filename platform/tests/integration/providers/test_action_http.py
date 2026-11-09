"""Separately running native API and actual MCP protocol service, without paid calls."""

from support.server import api_process


async def test_native_actions_use_real_mcp_http_service(secret_settings, tmp_path):
    async with api_process(
        secret_settings,
        tmp_path / "mcp.log",
        factory="support.mcp_service:create_app",
        health_path="/health",
    ) as mcp:
        async with api_process(secret_settings, tmp_path / "api.log") as api:
            results = {}
            for uid in ("mcp.get_tools_names", "mcp.validate_connection"):
                response = await api.post(
                    "/api/actions/action.execute",
                    json={
                        "uid": uid,
                        "inputData": {"mcp_url": str(mcp.base_url).rstrip("/") + "/mcp"},
                    },
                )
                assert response.status_code == 200 and response.json()["success"], response.text
                results[uid] = response.json()
            assert set(results["mcp.get_tools_names"]["tool_names"]) == {
                "read_remote_evidence",
                "read_failure",
            }
            assert results["mcp.validate_connection"]["is_reachable"]
