"""Protect portable configuration and resolve credentials for local execution and inspection."""

from typing import Any

from pydantic import BaseModel, JsonValue, SecretStr, TypeAdapter

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.drafts import ConfigurationDraft
from flareward.elements.construction.resolver import ElementBundleResolver
from flareward.resources.domain.bundles import BundleEntry, ElementBundle, ResourceDefinition
from flareward.resources.secrets import (
    ConfigurationSecretStore,
    is_secret_reference,
    protected_configuration,
    public_default,
    secret_text,
    sensitive_fields,
    serialized_key,
)
from flareward.services.identity.domain import Identity

_CONFIGURATION = TypeAdapter(dict[str, JsonValue])


class ConfigurationSecrets:
    def __init__(self, elements: ElementRegistry, store: ConfigurationSecretStore | None) -> None:
        self._elements, self._store = elements, store

    async def protect_resource(
        self, resource: ResourceDefinition, owner: Identity, *, allow_incomplete: bool = False
    ) -> ResourceDefinition:
        schema = self._elements.get_schema(resource.key.category, resource.type_key)
        try:
            configuration = (
                ConfigurationDraft.parse(schema, resource.config)
                if allow_incomplete
                else schema.model_validate(resource.config, by_name=True)
            )
        except ValueError:
            raise ValueError(f"Invalid configuration for {resource.type_key}") from None
        data = _CONFIGURATION.validate_python(
            await self._map(configuration, owner, protect=True, allow_incomplete=allow_incomplete),
            strict=True,
        )
        return resource.model_copy(update={"config": data}, deep=True)

    async def protect_draft(
        self, schema: type[BaseModel], data: dict[str, JsonValue], owner: Identity
    ) -> dict[str, JsonValue]:
        configuration = ConfigurationDraft.parse(schema, data)
        return _CONFIGURATION.validate_python(
            await self._map(configuration, owner, protect=True, allow_incomplete=True), strict=True
        )

    async def protect(self, configuration: BaseModel, owner: Identity) -> dict[str, JsonValue]:
        return _CONFIGURATION.validate_python(
            await self._map(configuration, owner, protect=True), strict=True
        )

    async def resolve(self, configuration: BaseModel, owner: Identity) -> dict[str, JsonValue]:
        return _CONFIGURATION.validate_python(
            await self._map(configuration, owner, protect=False), strict=True
        )

    async def resolve_authored(
        self, configuration: BaseModel, owner: Identity
    ) -> dict[str, JsonValue]:
        """Inspect local authoring data without persisting literals or exporting resolved values."""
        return _CONFIGURATION.validate_python(
            await self._map(configuration, owner, protect=False, authored=True), strict=True
        )

    async def _map(
        self,
        model: BaseModel | ConfigurationDraft,
        owner: Identity,
        *,
        protect: bool,
        authored: bool = False,
        allow_incomplete: bool = False,
    ) -> Any:
        if isinstance(model, ElementBundle):
            if not protect:
                return model.model_dump(mode="json")
            resources = [
                await self.protect_resource(
                    entry.resource, owner, allow_incomplete=allow_incomplete
                )
                for entry in model.entries
            ]
            try:
                return (
                    ElementBundleResolver(self._elements)
                    .resolve(model.root, resources)
                    .model_dump(mode="json")
                )
            except ValueError, KeyError:
                if not allow_incomplete:
                    raise
                return ElementBundle(
                    root=model.root,
                    entries=tuple(
                        BundleEntry(resource=resource, dependencies=entry.dependencies)
                        for resource, entry in zip(resources, model.entries, strict=True)
                    ),
                ).model_dump(mode="json")
        if protect and isinstance(model, ResourceDefinition):
            return (
                await self.protect_resource(model, owner, allow_incomplete=allow_incomplete)
            ).model_dump(mode="json")
        schema = model.schema if isinstance(model, ConfigurationDraft) else type(model)
        data = (
            ConfigurationDraft.serialize(model)
            if isinstance(model, ConfigurationDraft)
            else model.model_dump(mode="json")
        )
        if not isinstance(data, dict):
            return data
        sensitive = sensitive_fields(schema)
        for name, field in schema.model_fields.items():
            if name not in data:
                continue
            value = (
                model.values[name]
                if isinstance(model, ConfigurationDraft)
                else getattr(model, name)
            )
            if name in sensitive:
                raw = secret_text(value)
                data[name] = raw
                if isinstance(raw, str) and is_secret_reference(raw):
                    if self._store is None:
                        raise ValueError("Configuration secret storage is not configured")
                    secret = await self._store.get(owner, raw)
                    data[name] = raw if protect else secret.get_secret_value()
                elif isinstance(raw, str) and not public_default(raw, field.default):
                    if not protect and authored:
                        continue
                    if not protect or self._store is None:
                        raise ValueError("Literal configuration credentials require secret storage")
                    data[name] = await self._store.put(owner, SecretStr(raw))
            else:
                data[name] = await self._nested(
                    value,
                    data[name],
                    owner,
                    protect=protect,
                    authored=authored,
                    allow_incomplete=allow_incomplete,
                )
        if protect:
            if isinstance(model, ConfigurationDraft):
                if model.schema is ElementBundle:
                    data.pop("content_digest", None)
                return data
            # Validate the portable shape, including SecretStr serializers, after replacement.
            return protected_configuration(type(model).model_validate(data, by_name=True))
        return data

    async def _nested(
        self,
        value: Any,
        serialized: Any,
        owner: Identity,
        *,
        protect: bool,
        authored: bool,
        allow_incomplete: bool = False,
    ) -> Any:
        if isinstance(value, (BaseModel, ConfigurationDraft)):
            return await self._map(
                value, owner, protect=protect, authored=authored, allow_incomplete=allow_incomplete
            )
        if isinstance(value, (list, tuple)):
            return [
                await self._nested(
                    item,
                    encoded,
                    owner,
                    protect=protect,
                    authored=authored,
                    allow_incomplete=allow_incomplete,
                )
                for item, encoded in zip(value, serialized, strict=True)
            ]
        if isinstance(value, dict):
            return {
                serialized_key(key): await self._nested(
                    item,
                    serialized[serialized_key(key)],
                    owner,
                    protect=protect,
                    authored=authored,
                    allow_incomplete=allow_incomplete,
                )
                for key, item in value.items()
            }
        return serialized
