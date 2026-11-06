"""Durable policy cannot silently become process-local enforcement."""

import pytest
from mas.domain.execution.budgets import WorkLimits
from pydantic import ValidationError
from runengine.adapters.coordination.config import LocalHostConfig

from config.platform_settings import PlatformSettings


def test_work_limits_refuse_nondurable_platform_storage():
    with pytest.raises(ValidationError, match="durable Mongo"):
        PlatformSettings(
            host=LocalHostConfig(),
            storage="memory",
            authentication="development",
            development_user="owner",
            work_limits=WorkLimits(),
        )
