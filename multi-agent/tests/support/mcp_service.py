"""An actual MCP protocol service owned by integration tests."""

import os

from mcp.server.fastmcp import FastMCP
from starlette.responses import JSONResponse
from starlette.routing import Route


def create_app():
    evidence = os.environ.get("UNIFAI_TEST_MCP_EVIDENCE", "wire-evidence")
    calls = []
    server = FastMCP("Evidence", stateless_http=True, json_response=True, log_level="ERROR")

    @server.tool()
    async def read_remote_evidence() -> dict[str, str]:
        """Read evidence supplied by the actual MCP service."""
        calls.append("read_remote_evidence")
        return {"evidence": evidence, "source": "mcp-protocol"}

    @server.tool()
    async def read_failure() -> str:
        """Return a failed tool result over the MCP wire."""
        raise RuntimeError("remote-private-detail")

    async def health(request):
        return JSONResponse({"calls": calls})

    app = server.streamable_http_app()
    app.routes.append(Route("/health", health))
    return app
