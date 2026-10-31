"""Protect portable configuration and resolve credentials for local execution and inspection."""

from typing import Any

from pydantic import BaseModel, SecretStr, ValidationError

from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.resolver import ElementBundleResolver
from mas.core.identity import Identity
from mas.core.secrets import (
    ConfigurationSecretStore,
    is_secret_reference,
    protected_configuration,
    public_default,
    secret_text,
    sensitive_fields,
    serialized_key,
)
from mas.domain.element_bundles import ElementBundle, ResourceDefinition


class ConfigurationSecrets:
    def __init__(self, elements: ElementRegistry, store: ConfigurationSecretStore | None) -> None:
        self._elements, self._store = elements, store

    async def protect_resource(
        self, resource: ResourceDefinition, owner: Identity
    ) -> ResourceDefinition:
        schema = self._elements.get_schema(resource.key.category, resource.type_key)
        try:
            configuration = schema.model_validate(resource.config, by_name=True)
        except ValidationError:
            raise ValueError(f"Invalid configuration for {resource.type_key}") from None
        data = await self._map(configuration, owner, protect=True)
        return resource.model_copy(update={"config": data}, deep=True)

    async def protect(self, configuration: BaseModel, owner: Identity) -> dict:
        return await self._map(configuration, owner, protect=True)

    async def resolve(self, configuration: BaseModel, owner: Identity) -> dict:
        return await self._map(configuration, owner, protect=False)

    async def resolve_authored(self, configuration: BaseModel, owner: Identity) -> dict:
        """Inspect local authoring data without persisting literals or exporting resolved values."""
        return await self._map(configuration, owner, protect=False, authored=True)

    async def _map(
        self, model: BaseModel, owner: Identity, *, protect: bool, authored: bool = False
    ) -> Any:
        if isinstance(model, ElementBundle):
            if not protect:
                return model.model_dump(mode="json")
            resources = [
                await self.protect_resource(entry.resource, owner) for entry in model.entries
            ]
            return (
                ElementBundleResolver(self._elements)
                .resolve(model.root, resources)
                .model_dump(mode="json")
            )
        data = model.model_dump(mode="json")
        if not isinstance(data, dict):
            return data
        sensitive = sensitive_fields(type(model))
        for name, field in type(model).model_fields.items():
            if name not in data:
                continue
            value = getattr(model, name)
            if name in sensitive:
                raw = secret_text(value)
                data[name] = raw
                if is_secret_reference(raw):
                    if self._store is None:
                        raise ValueError("Configuration secret storage is not configured")
                    secret = await self._store.get(owner, raw)
                    data[name] = raw if protect else secret.get_secret_value()
                elif not public_default(raw, field.default):
                    if not protect and authored:
                        continue
                    if not protect or self._store is None:
                        raise ValueError("Literal configuration credentials require secret storage")
                    data[name] = await self._store.put(owner, SecretStr(raw))
            else:
                data[name] = await self._nested(
                    value, data[name], owner, protect=protect, authored=authored
                )
        if protect:
            # Validate the portable shape, including SecretStr serializers, after replacement.
            return protected_configuration(type(model).model_validate(data, by_name=True))
        return data

    async def _nested(
        self, value: Any, serialized: Any, owner: Identity, *, protect: bool, authored: bool
    ) -> Any:
        if isinstance(value, BaseModel):
            return await self._map(value, owner, protect=protect, authored=authored)
        if isinstance(value, (list, tuple)):
            return [
                await self._nested(item, encoded, owner, protect=protect, authored=authored)
                for item, encoded in zip(value, serialized, strict=True)
            ]
        if isinstance(value, dict):
            return {
                serialized_key(key): await self._nested(
                    item, serialized[serialized_key(key)], owner, protect=protect, authored=authored
                )
                for key, item in value.items()
            }
        return serialized
