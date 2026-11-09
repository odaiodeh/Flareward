"""Live-fixture profiles retain concrete SDK contracts and never enable host evaluation."""

import warnings

import pytest
from runengine.invocation.config import K8sRunnerConfig, OpenShellRunnerConfig, ThreadRunnerConfig
from support.live_feature import evaluation_target

from flareward.bootstrap.settings.platform_settings import PlatformSettings


@pytest.mark.parametrize(
    "target",
    [
        OpenShellRunnerConfig(endpoint="127.0.0.1:8090", image="fixture"),
        K8sRunnerConfig(image="fixture", namespace="owned-fixture"),
    ],
)
def test_evaluation_profile_retains_sdk_type_and_serializes_without_loss(target):
    original = target.model_dump(mode="json")
    prepared = evaluation_target(target)
    assert type(prepared) is type(target)
    assert target.model_dump(mode="json") == original
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        settings = PlatformSettings(
            host={"runner_type": "local"},
            storage="memory",
            interactions="disabled",
            authentication="development",
            development_user="owner",
            execution_profiles={"evaluation": prepared},
            default_execution_profile="evaluation",
        )
        encoded = settings.model_dump(mode="json")["execution_profiles"]["evaluation"]
    assert encoded == prepared.model_dump(mode="json")
    assert encoded["env"]["FLAREWARD_PYTHON_CHECK_EXECUTION_ENABLED"] == "true"
    assert encoded["env"]["FLAREWARD_CONFIGURATION_SECRETS"] == "false"
    assert "FLAREWARD_SECRETS_DIR" not in encoded["env"]
    if isinstance(prepared, OpenShellRunnerConfig):
        assert encoded["policy"]["network_policies"] == {}
        assert encoded["policy"]["landlock"]["compatibility"] == "best_effort"
        assert encoded["endpoint"] == original["endpoint"]
    else:
        assert encoded["namespace"] == original["namespace"]
        assert not encoded["secret_mounts"]


def test_host_profile_cannot_be_enabled_as_live_candidate_evaluation():
    with pytest.raises(ValueError, match="isolated deployment"):
        evaluation_target(ThreadRunnerConfig())
