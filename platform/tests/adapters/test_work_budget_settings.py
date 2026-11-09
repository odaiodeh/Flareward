"""Durable policy cannot silently become process-local enforcement."""

import pytest
from pydantic import ValidationError
from runengine.adapters.coordination.config import LocalHostConfig

from flareward.bootstrap.settings.platform_settings import PlatformSettings
from flareward.executions.domain.budgets import WorkLimits


def test_work_limits_refuse_nondurable_platform_storage():
    with pytest.raises(ValidationError, match="durable Mongo"):
        PlatformSettings(
            host=LocalHostConfig(),
            storage="memory",
            authentication="development",
            development_user="owner",
            work_limits=WorkLimits(),
        )
