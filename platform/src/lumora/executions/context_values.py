from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict, Field


class RunContext(BaseModel):
    """Immutable metadata about one graph-execution run."""

    user_id: str
    run_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    engine_name: Optional[str] = None

    started_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    finished_at: Optional[datetime] = None

    metadata: Dict[str, Any] = Field(default_factory=dict)
    tags: Dict[str, Any] = Field(default_factory=dict)
    scope: Optional[str] = "public"
    logged_in_user: Optional[str] = ""

    model_config = ConfigDict(frozen=True)

    def change_scope(self, new_scope: str) -> RunContext:
        return self.model_copy(update={"scope": new_scope})

    def set_logged_in_user(self, logged_in_user: str) -> RunContext:
        return self.model_copy(update={"logged_in_user": logged_in_user})

    def mark_finished(self) -> RunContext:
        return self.model_copy(update={"finished_at": datetime.now(timezone.utc)})

    def with_metadata(self, **entries) -> RunContext:
        new_md = {**self.metadata, **entries}
        return self.model_copy(update={"metadata": new_md})
