"""Reuse category factories with per-invocation resource ownership."""

import asyncio
import inspect
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from mas.application.elements.builder import SessionElementBuilder
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.application.elements.instances import ElementInstances
from mas.application.elements.lifecycle import ElementPreparation
from mas.core.async_work import await_owned
from mas.core.element_deps import ElementBuildContext
from mas.core.ref.models import Ref
from mas.core.resource_models import ResourceSpec
from mas.core.secrets import configuration_secret_references
from mas.domain.element_bundles import ElementBundle


@dataclass(frozen=True)
class BuiltElement:
    element: Any
    registry: ElementInstances
    protected: bool = False


class ElementBundleBuilder:
    def __init__(self, registry: ElementRegistry) -> None:
        self._registry = registry
        self._builders = SessionElementBuilder(registry).resource_builders

    @asynccontextmanager
    async def build(
        self,
        bundle: ElementBundle,
        deps: ElementBuildContext | None = None,
    ) -> AsyncIterator[BuiltElement]:
        # Revalidate both digest and actual typed edges; never trust caller-supplied edges.
        bundle = ElementBundle.model_validate(bundle.model_dump(mode="json"))
        resolved = ElementBundleResolver(self._registry).resolve(
            bundle.root,
            (entry.resource for entry in bundle.entries),
        )
        if resolved != bundle:
            raise ValueError("Bundle dependency metadata does not match its configuration")
        registry = ElementInstances()
        owned: list[tuple[Any, bool]] = []
        private_resources = set()
        primary_error: BaseException | None = None
        try:
            for entry in bundle.entries:
                resource = entry.resource
                schema = self._registry.get_schema(resource.key.category, resource.type_key)
                config = schema.model_validate(resource.config, by_name=True)
                protected = any(configuration_secret_references(config)) or any(
                    dependency in private_resources for dependency in entry.dependencies
                )
                if protected:
                    private_resources.add(resource.key)
                if protected and (deps is None or deps.execution_ctx is None):
                    raise ValueError(
                        "Protected configuration requires receiver identity and secret storage"
                    )
                if deps is not None and deps.execution_ctx is not None:
                    data = await ConfigurationSecrets(
                        self._registry, deps.configuration_secrets
                    ).resolve(config, deps.execution_ctx.context.identity)
                    try:
                        config = schema.model_validate(data, by_name=True)
                    except ValidationError:
                        raise ValueError(
                            f"Invalid protected configuration for {resource.type_key}"
                        ) from None
                spec = ResourceSpec(
                    rid=Ref.for_category(resource.key.category)(resource.key.rid),
                    name=resource.name,
                    type=resource.type_key,
                    config=config,
                )

                def construct() -> None:
                    instance = self._builders[resource.key.category].build_resource(
                        spec, registry, deps
                    )
                    if not any(existing is instance for existing, _ in owned):
                        owned.append((instance, protected))

                try:
                    await await_owned(asyncio.to_thread(construct))
                    instance = registry.get_instance(resource.key.category, resource.key.rid)
                    if isinstance(instance, ElementPreparation):
                        await instance.prepare_element()
                except Exception:
                    if protected:
                        raise ValueError(
                            f"Element construction failed for {resource.type_key}"
                        ) from None
                    raise
            registry.freeze()
            yield BuiltElement(
                registry.get_instance(bundle.root.category, bundle.root.rid),
                registry,
                bundle.root in private_resources,
            )
        except BaseException as error:
            primary_error = error
            raise
        finally:

            async def release() -> list[Exception]:
                errors: list[Exception] = []
                for instance, protected in reversed(owned):
                    close = getattr(instance, "aclose", None) or getattr(instance, "close", None)
                    if close is not None:
                        try:
                            if inspect.iscoroutinefunction(close):
                                await close()
                            else:
                                result = await asyncio.to_thread(close)
                                if inspect.isawaitable(result):
                                    await result
                        except Exception as error:
                            errors.append(
                                RuntimeError(
                                    f"Protected resource cleanup failed: {type(instance).__name__}"
                                )
                                if protected
                                else error
                            )
                return errors

            cleanup_errors = await await_owned(release())
            if cleanup_errors:
                group = ExceptionGroup("Element resource cleanup failed", cleanup_errors)
                if primary_error is not None:
                    primary_error.add_note(str(group))
                else:
                    raise group
