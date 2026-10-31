from typing import Annotated

from pydantic import Field

from .router_boolean.config import RouterBooleanConditionConfig
from .router_direct.config import RouterDirectConditionConfig
from .threshold.config import ThresholdConditionConfig

ConditionSpec = Annotated[
    ThresholdConditionConfig | RouterDirectConditionConfig | RouterBooleanConditionConfig,
    Field(discriminator="type"),
]
