from dataclasses import dataclass, field

from mas.application.access.credentials import WorkflowCredentialSource
from mas.application.execution.context import ExecutionContextHolder
from mas.core.auth.service import AuthService
from mas.core.platform_config import PlatformConfig
from mas.core.secrets import ConfigurationSecretStore
from mas.core.tracing import TracingService


@dataclass
class ElementBuildContext:
    """Cross-cutting dependencies available during element construction.

    Carries stable services and runtime bridges that elements capture
    at build time.  NOT for per-run concerns (channel, HITL gate) —
    those flow through ``NodeRuntimeBinder`` at execution time.

    Adding a new build-time concern means adding one field here —
    no signature changes anywhere else.
    """

    execution_ctx: ExecutionContextHolder | None = field(default=None)
    auth_service: AuthService | None = field(default=None)
    platform_config: PlatformConfig | None = field(default=None)
    tracing_service: TracingService | None = field(default=None)
    configuration_secrets: ConfigurationSecretStore | None = None
    workflow_credentials: WorkflowCredentialSource | None = None
