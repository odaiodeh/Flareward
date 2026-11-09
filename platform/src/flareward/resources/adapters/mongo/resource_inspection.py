"""Own blocking library reads and installed provider probes through request cancellation."""

import asyncio
from collections.abc import Awaitable, Callable
from functools import partial

from pydantic import JsonValue, ValidationError
from pymongo.errors import PyMongoError

from flareward.async_work import await_owned
from flareward.elements.domain.cards import ElementCard
from flareward.elements.exceptions import ElementInspectionError
from flareward.elements.validation import ElementValidationResult
from flareward.resources.builtin_aware_service import BuiltinAwareResourceService
from flareward.resources.domain.categories import ResourceCategory
from flareward.resources.errors import ResourceStorageError
from flareward.resources.probes import InspectionContext
from flareward.resources.resolver import ResourceDependencyError


async def inspect_owned[T](operation: Callable[[], T]) -> T:
    return await inspect_async(await_owned(asyncio.to_thread(operation)))


async def inspect_async[T](operation: Awaitable[T]) -> T:
    try:
        return await operation
    except PyMongoError:
        raise ResourceStorageError() from None
    except ValidationError:
        raise ValueError("Invalid resource configuration") from None
    except KeyError, PermissionError:
        raise
    except ResourceDependencyError:
        raise
    except Exception:
        # Installed plugins may include credentials in SDK failures. This boundary
        # reports a failed inspection without exporting their exception details.
        raise ElementInspectionError() from None


class StoredResourceProbe:
    def __init__(self, resources: BuiltinAwareResourceService) -> None:
        self._resources = resources

    async def validate(
        self,
        rids: list[str],
        context: InspectionContext,
        *,
        timeout_seconds: float = 10,
    ) -> list[ElementValidationResult]:
        semaphore = asyncio.Semaphore(10)

        async def validate_one(rid: str) -> ElementValidationResult:
            async with semaphore:
                try:
                    return await inspect_async(
                        self._resources.validate_resource_async(
                            rid,
                            caller=context.scope,
                            user_id=context.owner.id,
                            credential_user_id=context.credential_user_id,
                            timeout_seconds=timeout_seconds,
                        )
                    )
                except KeyError:
                    return ElementValidationResult.create_error(rid, "Resource not found")

        # Drain every started probe even if one fails. Library clients remain owned
        # until all sibling work exits; no request can abandon background probes.
        tasks = [asyncio.create_task(validate_one(rid)) for rid in rids]

        def cancel_tasks() -> None:
            for task in tasks:
                task.cancel()

        results = await await_owned(
            asyncio.gather(*tasks, return_exceptions=True),
            on_cancel=cancel_tasks,
        )
        values: list[ElementValidationResult] = []
        for result in results:
            if isinstance(result, BaseException):
                raise result
            values.append(result)
        return values

    async def validate_config(
        self,
        category: ResourceCategory,
        type_key: str,
        config: dict[str, JsonValue],
        context: InspectionContext,
        *,
        name: str | None = None,
        timeout_seconds: float = 10,
    ) -> ElementValidationResult:
        return await inspect_async(
            self._resources.validate_config_async(
                category.value,
                type_key,
                config,
                name,
                timeout_seconds,
                caller=context.scope,
                user_id=context.owner.id,
                credential_user_id=context.credential_user_id,
            )
        )

    async def cards(self, rids: list[str], context: InspectionContext) -> dict[str, ElementCard]:
        return await inspect_owned(partial(self._resources.get_cards, rids, caller=context.scope))
