"""Run inside the production image: canonical CLI, HTTP, native Wait and cleanup."""

import asyncio
import json
import os
import signal
import subprocess
import tempfile
from uuid import uuid4

import httpx
from pymongo import AsyncMongoClient
from temporalio.api.enums.v1 import TaskQueueType
from temporalio.api.taskqueue.v1 import TaskQueue
from temporalio.api.workflowservice.v1 import DescribeTaskQueueRequest
from temporalio.client import Client


async def main():
    host = os.environ.get("FLAREWARD_SMOKE_HOST", '{"runner_type":"local"}')
    selected = json.loads(host)
    durable = selected["runner_type"] == "temporal"
    database = "flareward_platform_image_" + uuid4().hex
    mongo = os.environ.get("FLAREWARD_SMOKE_MONGO_URI", "mongodb://mongo:27017")
    if selected["runner_type"] == "temporal":
        namespace = selected.get("namespace", "default")
        client = await Client.connect(selected["endpoint"], namespace=namespace)
        async with asyncio.timeout(30):
            while True:
                queue = await client.workflow_service.describe_task_queue(
                    DescribeTaskQueueRequest(
                        namespace=namespace,
                        task_queue=TaskQueue(name=selected["task_queue"]),
                        task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
                    )
                )
                if queue.pollers:
                    break
                await asyncio.sleep(0.05)
    environment = dict(
        os.environ,
        FLAREWARD_HOST=host,
        FLAREWARD_STORAGE="mongo" if durable else "memory",
        FLAREWARD_MONGO_URI=mongo,
        FLAREWARD_MONGO_DATABASE=database,
        FLAREWARD_AUTHENTICATION="development",
        FLAREWARD_DEVELOPMENT_USER="image-smoke",
        FLAREWARD_INTERACTIONS="disabled",
    )
    with tempfile.TemporaryFile(mode="w+") as log:
        server = subprocess.Popen(
            ["flareward-platform", "serve", "--host", "127.0.0.1", "--port", "13457"],
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
        try:
            async with httpx.AsyncClient(base_url="http://127.0.0.1:13457", timeout=5) as http:
                async with asyncio.timeout(30):
                    while True:
                        if server.poll() is not None:
                            log.seek(0)
                            raise AssertionError(log.read())
                        try:
                            response = await http.get("/api/health/health")
                        except httpx.ConnectError:
                            await asyncio.sleep(0.05)
                        else:
                            assert response.status_code == 200, response.text
                            break
                    definition = {
                        "program_id": "image-wait",
                        "name": "Image wait",
                        "owner": {
                            "type": "user",
                            "id": "image-smoke",
                            "display_name": "image-smoke",
                        },
                        "implementation": {
                            "kind": "application",
                            "implementation": "wait",
                            "version": "1",
                            "config": {"channel": "answer", "timeout_seconds": 0.02},
                        },
                    }
                    saved = await http.put(
                        "/api/programs/image-wait",
                        json={"definition": definition, "expected_version": 0},
                    )
                    assert saved.status_code == 200, saved.text
                    published = await http.post(
                        "/api/programs/image-wait/revisions",
                        json={"expected_version": saved.json()["version"]},
                    )
                    assert published.status_code == 201, published.text
                    execution_id = "image-smoke-" + uuid4().hex
                    started = await http.post(
                        "/api/executions",
                        json={
                            "program": {
                                "program_id": "image-wait",
                                "revision": published.json()["revision"],
                            },
                            "execution_id": execution_id,
                            "inputs": {},
                        },
                    )
                    assert started.status_code == 202, started.text
                    result = await http.get(f"/api/executions/{execution_id}/result")
                    assert result.status_code == 200, result.text
                    assert result.json()["phase"] == "completed", result.text
                    assert result.json()["result"]["reason"] == "timed_out", result.text
                    print("Image HTTP admission, publication and native Wait passed", flush=True)
        finally:
            server.terminate()
            code = await asyncio.to_thread(server.wait, timeout=15)
            log.seek(0)
            data = log.read()
            if durable:
                storage = AsyncMongoClient(mongo, serverSelectionTimeoutMS=5000)
                try:
                    await storage.drop_database(database)
                finally:
                    await storage.close()
            assert code in (0, -signal.SIGTERM) and "Application shutdown complete" in data, data


if __name__ == "__main__":
    asyncio.run(main())
