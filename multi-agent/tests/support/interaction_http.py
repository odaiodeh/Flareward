"""Observe actual application approval tickets without importing test scenarios."""

import asyncio

import httpx


async def pending(http: httpx.AsyncClient, root: str) -> dict:
    async with asyncio.timeout(8):
        while True:
            response = await http.get(f"/api/executions/{root}/approvals")
            assert response.status_code == 200, response.text
            if response.json():
                return response.json()[0]
            status = await http.get(f"/api/executions/{root}")
            assert status.json()["phase"] not in {"failed", "completed", "cancelled"}, status.text
            await asyncio.sleep(0.02)
