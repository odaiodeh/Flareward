"""Resolve library authoring data off-loop; inspection behavior remains in the application."""

import asyncio
from typing import cast

from pydantic import BaseModel, ValidationError
from pymongo.errors import PyMongoError

from flareward.async_work import await_owned
from flareward.programs.templates.contracts import (
    BlueprintData,
    BlueprintResolution,
    BlueprintTemplate,
)
from flareward.programs.templates.exceptions import BlueprintStorageError
from flareward.programs.templates.resolver import BlueprintResolver
from flareward.services.identity.domain import Identity
from flareward.services.identity.scope import CallerScope


class StoredBlueprintResolution:
    def __init__(self, resolver: BlueprintResolver, draft_schema: type[BaseModel]) -> None:
        self._resolver = resolver
        self._draft_schema = draft_schema

    async def resolve(
        self, spec: BlueprintData, caller: Identity, *, stored: bool
    ) -> BlueprintResolution:
        def resolve() -> BlueprintResolution:
            data = (
                {
                    key: value
                    for key, value in spec.items()
                    if key in self._draft_schema.model_fields
                }
                if stored
                else spec
            )
            draft = cast(BlueprintTemplate, self._draft_schema.model_validate(data, by_name=True))
            resolved, missing = self._resolver.resolve_tolerant(draft, CallerScope(identity=caller))
            return BlueprintResolution(resolved, missing)

        try:
            return await await_owned(asyncio.to_thread(resolve))
        except ValidationError:
            raise ValueError("Invalid blueprint configuration") from None
        except PyMongoError:
            raise BlueprintStorageError() from None
