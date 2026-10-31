"""Own one test namespace without mutating the global Kubernetes context."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from kubernetes import client, config
from mas.core.async_work import await_owned
from runengine.invocation.config import K8sRunnerConfig, SecretMount

from support.deployment_backend import DeploymentBackend, NetworkEndpoint


@asynccontextmanager
async def backend() -> AsyncIterator[DeploymentBackend]:
    context, image = (
        os.environ[name] for name in ("UNIFAI_TEST_K8S_CONTEXT", "UNIFAI_TEST_K8S_IMAGE")
    )
    kubeconfig = os.environ.get("UNIFAI_TEST_KUBECONFIG")
    namespace = "unifai-e2e-" + uuid4().hex[:16]
    api = await asyncio.to_thread(
        config.new_client_from_config, config_file=kubeconfig, context=context
    )
    core, batch = client.CoreV1Api(api), client.BatchV1Api(api)
    created = False
    try:
        await asyncio.to_thread(
            core.create_namespace,
            client.V1Namespace(
                metadata=client.V1ObjectMeta(name=namespace, labels={"unifai-e2e-owner": namespace})
            ),
        )
        created = True

        async def assert_clean() -> None:
            async with asyncio.timeout(30):
                while True:
                    jobs = await asyncio.to_thread(batch.list_namespaced_job, namespace)
                    pods = await asyncio.to_thread(core.list_namespaced_pod, namespace)
                    if not jobs.items and not pods.items:
                        return
                    await asyncio.sleep(0.2)

        target = K8sRunnerConfig(
            image=image,
            namespace=namespace,
            kubeconfig_path=kubeconfig,
            kubeconfig_context=context,
            timeout=90,
            labels={"unifai-e2e-owner": namespace},
            env={"UNIFAI_INTERACTIONS": "disabled"},
        )

        @asynccontextmanager
        async def configured(
            values: dict[str, str], endpoints: tuple[NetworkEndpoint, ...]
        ) -> AsyncIterator[K8sRunnerConfig]:
            # This isolated kind namespace has no egress-denying NetworkPolicy.
            name, directory = "receiver-settings", "/var/run/unifai-settings"
            await asyncio.to_thread(
                core.create_namespaced_secret,
                namespace,
                client.V1Secret(
                    metadata=client.V1ObjectMeta(name=name),
                    string_data=values,
                ),
            )
            try:
                yield target.model_copy(
                    update={
                        "secret_mounts": [SecretMount(secret_name=name, mount_path=directory)],
                        "env": {**(target.env or {}), "UNIFAI_SECRETS_DIR": directory},
                    }
                )
            finally:
                await await_owned(asyncio.to_thread(core.delete_namespaced_secret, name, namespace))

        yield DeploymentBackend(
            "k8s",
            target,
            assert_clean,
            configured,
            namespace,
        )
    finally:
        try:
            if created:
                await await_owned(asyncio.to_thread(core.delete_namespace, namespace))
        finally:
            await await_owned(asyncio.to_thread(api.close))
