"""Portable native schedule action; application services do not interpret its runtime data."""

from mas.scheduling.programs import ScheduleRegistration
from pydantic import BaseModel, ConfigDict
from runengine.core.refs import FunctionRef


class ScheduledProgramInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration: ScheduleRegistration
    admission: FunctionRef
