"""Resolve library authoring data off-loop; inspection behavior remains in the application."""

import asyncio
from typing import cast

from pydantic import BaseModel, ValidationError
from pymongo.errors import PyMongoError

from lumora.async_work import await_owned
from lumora.programs.templates.contracts import (
    BlueprintData,
    BlueprintResolution,
    BlueprintTemplate,
)
from lumora.programs.templates.exceptions import BlueprintStorageError
from lumora.programs.templates.resolver import BlueprintResolver
from lumora.services.identity.domain import Identity
from lumora.services.identity.scope import CallerScope


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
