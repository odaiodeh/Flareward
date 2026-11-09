"""Scenario-facing backend evidence; SDK ownership stays in backend-specific fixtures."""

from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass

from runengine.invocation.config import ExecutorConfig


@dataclass(frozen=True)
class NetworkEndpoint:
    host: str
    port: int
    binaries: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReceiverEvidence:
    namespace: str
    pod: str
    image: str
    image_id: str
    non_root: bool
    host_access: bool
    mounted_secrets: bool
    environment_names: frozenset[str]


@dataclass(frozen=True)
class DeploymentBackend:
    name: str
    target: ExecutorConfig
    assert_clean: Callable[[], Awaitable[None]]
    configured: Callable[
        [dict[str, str], tuple[NetworkEndpoint, ...]], AbstractAsyncContextManager[ExecutorConfig]
    ]
    namespace: str | None = None
    inspect_receiver: Callable[[], Awaitable[ReceiverEvidence]] | None = None

    def verify(self, proof: dict) -> None:
        assert proof["system"] == "Linux"
        assert proof["hostname"] and proof["pid"] > 0
        assert proof["image_marker"] == "flareward-platform-e2e-v1"
        assert proof["namespace"] == self.namespace
        assert proof["dependencies"] == ["middle", "leaf"]
