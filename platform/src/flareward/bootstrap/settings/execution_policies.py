"""Load operator-owned policy files before acquiring platform resources."""

import asyncio
from pathlib import Path

from runengine.invocation.config import OpenShellPolicy, OpenShellRunnerConfig

from flareward.async_work import await_owned
from flareward.bootstrap.settings.platform_settings import PlatformSettings, RunnerSettings


def _read_policy(path: Path, profile: str) -> OpenShellPolicy:
    try:
        return OpenShellPolicy.model_validate_json(path.read_text(encoding="utf-8"))
    except OSError, ValueError:
        # Validation errors can contain whole input documents. Keep deployment
        # errors actionable without logging policy contents or incidental secrets.
        raise ValueError(f"Cannot load execution policy for profile {profile!r}: {path}") from None


async def load_execution_profiles(settings: PlatformSettings) -> dict[str, RunnerSettings]:
    """Detach a startup snapshot; neither agents nor retries read policy files."""
    settings = PlatformSettings.model_validate(dict(settings))
    profiles = {
        name: target.model_copy(deep=True) for name, target in settings.execution_profiles.items()
    }
    for name, path in settings.execution_policy_files.items():
        policy = await await_owned(asyncio.to_thread(_read_policy, path, name))
        profiles[name] = OpenShellRunnerConfig.model_validate(
            {**profiles[name].model_dump(mode="python"), "policy": policy}
        )
    return profiles
