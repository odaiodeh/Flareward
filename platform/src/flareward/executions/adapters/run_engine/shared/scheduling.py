"""Portable native schedule action; application services do not interpret its runtime data."""

from pydantic import BaseModel, ConfigDict
from runengine.core.refs import FunctionRef

from flareward.services.scheduling.programs import ScheduleRegistration


class ScheduledProgramInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    registration: ScheduleRegistration
    admission: FunctionRef
