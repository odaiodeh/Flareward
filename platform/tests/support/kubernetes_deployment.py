"""Own one test namespace without mutating the global Kubernetes context."""

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from uuid import uuid4

from kubernetes import client, config
from runengine.invocation.config import K8sRunnerConfig, SecretMount

from flareward.async_work import await_owned
from support.deployment_backend import DeploymentBackend, NetworkEndpoint, ReceiverEvidence


@asynccontextmanager
async def backend() -> AsyncIterator[DeploymentBackend]:
    context, image = (
        os.environ[name] for name in ("FLAREWARD_TEST_K8S_CONTEXT", "FLAREWARD_TEST_K8S_IMAGE")
    )
    kubeconfig = os.environ.get("FLAREWARD_TEST_KUBECONFIG")
    namespace = "flareward-e2e-" + uuid4().hex[:16]
    api = await asyncio.to_thread(
        config.new_client_from_config, config_file=kubeconfig, context=context
    )
    core, batch = client.CoreV1Api(api), client.BatchV1Api(api)
    created = False
    try:
        await asyncio.to_thread(
            core.create_namespace,
            client.V1Namespace(
                metadata=client.V1ObjectMeta(
                    name=namespace, labels={"flareward-e2e-owner": namespace}
                )
            ),
        )
        created = True
        await asyncio.to_thread(
            core.create_namespaced_service_account,
            namespace,
            client.V1ServiceAccount(
                metadata=client.V1ObjectMeta(name="receiver"),
                automount_service_account_token=False,
            ),
        )

        async def inspect_receiver() -> ReceiverEvidence:
            async with asyncio.timeout(45):
                while True:
                    pods = await asyncio.to_thread(core.list_namespaced_pod, namespace)
                    for pod in pods.items:
                        statuses = pod.status.container_statuses or []
                        if not statuses or not statuses[0].image_id:
                            continue
                        container = pod.spec.containers[0]
                        return ReceiverEvidence(
                            namespace=namespace,
                            pod=pod.metadata.name,
                            image=container.image,
                            image_id=statuses[0].image_id,
                            non_root=bool(container.security_context.run_as_non_root),
                            host_access=bool(
                                pod.spec.host_network
                                or pod.spec.host_pid
                                or pod.spec.host_ipc
                                or any(v.host_path for v in pod.spec.volumes or [])
                            ),
                            mounted_secrets=any(
                                v.secret or v.projected for v in pod.spec.volumes or []
                            ),
                            environment_names=frozenset(v.name for v in container.env or []),
                        )
                    await asyncio.sleep(0.05)

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
            service_account="receiver",
            kubeconfig_path=kubeconfig,
            kubeconfig_context=context,
            timeout=90,
            labels={"flareward-e2e-owner": namespace},
            env={"FLAREWARD_INTERACTIONS": "disabled", "FLAREWARD_TEST_NAMESPACE": namespace},
        )

        @asynccontextmanager
        async def configured(
            values: dict[str, str], endpoints: tuple[NetworkEndpoint, ...]
        ) -> AsyncIterator[K8sRunnerConfig]:
            # This isolated kind namespace has no egress-denying NetworkPolicy.
            name, directory = "receiver-settings", "/var/run/flareward-settings"
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
                        "env": {**(target.env or {}), "FLAREWARD_SECRETS_DIR": directory},
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
            inspect_receiver,
        )
    finally:
        try:
            if created:
                await await_owned(asyncio.to_thread(core.delete_namespace, namespace))
        finally:
            await await_owned(asyncio.to_thread(api.close))
