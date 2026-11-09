"""Own a unique sandbox workspace while using certificate-authenticated SDK clients."""

import asyncio
import json
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from uuid import uuid4

from openshell import SandboxClient, TlsConfig, WorkspaceClient
from openshell._proto import openshell_pb2
from runengine.invocation.config import OpenShellRunnerConfig, OpenShellTLSConfig

from flareward.async_work import await_owned
from support.deployment_backend import DeploymentBackend, NetworkEndpoint

WRITE_SETTINGS = """
import json
import sys
from pathlib import Path

directory = Path('/sandbox/.flareward-receiver-settings')
directory.mkdir(mode=0o700, exist_ok=True)
for name, value in json.load(sys.stdin).items():
    path = directory / name
    path.write_text(value)
    path.chmod(0o600)
"""


@asynccontextmanager
async def backend() -> AsyncIterator[DeploymentBackend]:
    pki = Path(os.environ["FLAREWARD_TEST_OPENSHELL_PKI"]).resolve()
    endpoint, image = (
        os.environ[name]
        for name in ("FLAREWARD_TEST_OPENSHELL_ENDPOINT", "FLAREWARD_TEST_OPENSHELL_IMAGE")
    )
    workspace = "fw-" + uuid4().hex[:12]
    paths = {
        "ca_path": str(pki / "ca.crt"),
        "cert_path": str(pki / "client.crt"),
        "key_path": str(pki / "client.key"),
    }
    connection = SandboxClient(
        endpoint, tls=TlsConfig(**{key: Path(value) for key, value in paths.items()})
    )
    workspaces = WorkspaceClient.from_sandbox_client(connection)
    created = False
    try:
        await asyncio.to_thread(connection.health)
        await asyncio.to_thread(workspaces.create, workspace)
        created = True

        async def assert_clean() -> None:
            async with asyncio.timeout(30):
                while await asyncio.to_thread(connection.list, workspace=workspace):
                    await asyncio.sleep(0.2)

        environment = {
            "FLAREWARD_INTERACTIONS": "disabled",
            "PATH": "/sandbox/.venv/bin:/usr/local/bin:/usr/bin:/bin",
            "PYTHONPATH": "/opt/test-fixtures",
        }

        @asynccontextmanager
        async def configured(
            values: dict[str, str], endpoints: tuple[NetworkEndpoint, ...]
        ) -> AsyncIterator[OpenShellRunnerConfig]:
            spec = openshell_pb2.SandboxSpec()
            spec.template.image = image
            # A supplied policy replaces the image policy, including filesystem/process setup.
            spec.policy.version = 1
            spec.policy.filesystem.include_workdir = True
            spec.policy.filesystem.read_only.extend(
                ["/usr", "/lib", "/proc", "/dev/urandom", "/app", "/etc", "/var/log", "/opt"]
            )
            spec.policy.filesystem.read_write.extend(["/sandbox", "/tmp", "/dev/null"])
            spec.policy.landlock.compatibility = "best_effort"
            spec.policy.process.run_as_user = spec.policy.process.run_as_group = "sandbox"
            for index, service_endpoint in enumerate(endpoints):
                network = spec.policy.network_policies[f"receiver_service_{index}"]
                network.name = f"receiver-service-{index}"
                network.endpoints.add(
                    host=service_endpoint.host,
                    port=service_endpoint.port,
                )
                for binary in service_endpoint.binaries or (
                    "/sandbox/.venv/bin/python",
                    "/sandbox/.venv/bin/python3",
                    "/usr/local/bin/python3.14",
                ):
                    network.binaries.add(path=binary)
            reference = await asyncio.to_thread(connection.create, workspace=workspace, spec=spec)
            try:
                ready = await asyncio.to_thread(
                    connection.wait_ready, reference.name, workspace=workspace, timeout_seconds=90
                )
                installed = await asyncio.to_thread(
                    connection.exec,
                    ready.id,
                    ["python", "-c", WRITE_SETTINGS],
                    stdin=json.dumps(values).encode(),
                    env=environment,
                    timeout_seconds=30,
                )
                assert installed.exit_code == 0, "Receiver-local settings provisioning failed"
                yield OpenShellRunnerConfig(
                    endpoint=endpoint,
                    sandbox_id=ready.id,
                    workspace=workspace,
                    tls=OpenShellTLSConfig(**paths),
                    timeout_seconds=90,
                    env={
                        **environment,
                        "FLAREWARD_SECRETS_DIR": "/sandbox/.flareward-receiver-settings",
                    },
                )
            finally:
                deleted = await await_owned(
                    asyncio.to_thread(connection.delete, reference.name, workspace=workspace)
                )
                assert deleted, "Configured test sandbox was not deleted"
                await assert_clean()

        yield DeploymentBackend(
            "openshell",
            OpenShellRunnerConfig(
                endpoint=endpoint,
                image=image,
                workspace=workspace,
                tls=OpenShellTLSConfig(**paths),
                timeout_seconds=90,
                sandbox_ready_timeout=90,
                env=environment,
            ),
            assert_clean,
            configured,
        )
    finally:

        async def close():
            try:
                if created:
                    remaining = await asyncio.to_thread(connection.list, workspace=workspace)
                    for sandbox in remaining:
                        await asyncio.to_thread(
                            connection.delete, sandbox.name, workspace=workspace
                        )
                    await assert_clean()
                    await asyncio.to_thread(workspaces.delete, workspace)
            finally:
                await asyncio.to_thread(connection.close)

        await await_owned(close())
