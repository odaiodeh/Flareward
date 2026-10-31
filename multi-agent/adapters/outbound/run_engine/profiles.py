"""Project approved runner configuration into safe application placement metadata."""

from collections.abc import Mapping

from mas.core.execution_preferences import ExecutionProfileCatalog
from runengine.bootstrap.environments import EnvironmentFactory
from runengine.bootstrap.executors import InvocationExecutorBuilder
from runengine.invocation.config import ExecutorConfig


def supports_retained_environment(profile: ExecutorConfig) -> bool:
    factory = InvocationExecutorBuilder.environment_factory(profile.runner_type)
    return isinstance(factory, EnvironmentFactory)


def profile_catalog(
    profiles: Mapping[str, ExecutorConfig], default_profile: str
) -> ExecutionProfileCatalog:
    return ExecutionProfileCatalog(
        profiles=tuple(sorted(profiles)),
        default_profile=default_profile,
        environment_profiles=tuple(
            sorted(
                name for name, profile in profiles.items() if supports_retained_environment(profile)
            )
        ),
    )
