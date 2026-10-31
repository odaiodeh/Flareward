"""Resolve library authoring data off-loop; inspection behavior remains in the application."""

import asyncio
from typing import cast

from mas.blueprints.contracts import BlueprintData, BlueprintResolution, BlueprintTemplate
from mas.blueprints.exceptions import BlueprintStorageError
from mas.blueprints.resolver import BlueprintResolver
from mas.core.async_work import await_owned
from mas.core.caller_scope import CallerScope
from mas.core.identity import Identity
from pydantic import BaseModel, ValidationError
from pymongo.errors import PyMongoError


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
