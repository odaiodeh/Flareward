"""Normal plugin registration; execution enablement is receiver-owned policy."""

from pathlib import Path
from typing import Any, Self

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from flareward.elements.factory import BaseFactory
from flareward.elements.specification import BaseElementSpec
from flareward.resources.domain.categories import ResourceCategory
from plugins.testing.contracts import (
    PythonFunctionConfig,
    PythonFunctionInput,
    PythonFunctionResult,
)
from plugins.testing.python_functions import PythonFunctionEvaluation


class PythonCheckSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FLAREWARD_PYTHON_CHECK_", extra="ignore")
    execution_enabled: bool = False
    directory: Path = Path("/tmp/flareward-python-checks")

    @model_validator(mode="after")
    def absolute_directory(self) -> Self:
        if not self.directory.is_absolute():
            raise ValueError("Python check directory must be absolute")
        return self


class PythonFunctionFactory(BaseFactory[PythonFunctionConfig, PythonFunctionEvaluation]):
    def accepts(self, cfg: PythonFunctionConfig, element_type: str) -> bool:
        return element_type == "python_function_evaluate"

    def create(self, cfg: PythonFunctionConfig, **dependencies: Any) -> PythonFunctionEvaluation:
        settings = PythonCheckSettings()
        if not settings.execution_enabled:
            raise ValueError("Python checking is not enabled in this execution environment")
        return PythonFunctionEvaluation(cfg, settings.directory)


class PythonFunctionSpec(BaseElementSpec):
    version = "2.0.0"
    category = ResourceCategory.OPERATION
    type_key = "python_function_evaluate"
    name = "Evaluate Python functions"
    description = "Return bounded candidate values from an operator-approved execution environment"
    config_schema = PythonFunctionConfig
    factory_cls = PythonFunctionFactory
    input_schema = PythonFunctionInput
    result_schema = PythonFunctionResult


ELEMENT_SPECIFICATIONS = (PythonFunctionSpec,)
