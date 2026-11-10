"""Shared schema metadata and encrypted resource configuration, independent of storage SDKs."""

from typing import Any

from pydantic import AliasChoices, BaseModel, ValidationError
from pydantic.fields import FieldInfo

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.resources.domain.categories import ResourceCategory
from lumora.resources.secrets import map_configuration_secrets, public_default, sensitive_fields
from lumora.services.auth.credentials.ports import TokenCipher

AUTH_METADATA_OVERLAY_FIELDS = frozenset({"server_identifier", "scheme_type"})


def decrypt_values(value: Any, cipher: TokenCipher | None) -> Any:
    """Decode the reserved stored-string format and return detached configuration."""
    if isinstance(value, str) and cipher is not None:
        return cipher.decrypt(value)
    if isinstance(value, dict):
        return {key: decrypt_values(item, cipher) for key, item in value.items()}
    if isinstance(value, list):
        return [decrypt_values(item, cipher) for item in value]
    return value


def field_hints(field: FieldInfo) -> dict:
    extra = field.json_schema_extra
    return extra.get("hints", {}) if isinstance(extra, dict) else {}


class ResourceFieldEncryption:
    def __init__(self, element_registry: ElementRegistry, cipher: TokenCipher | None) -> None:
        self._element_registry, self._cipher = element_registry, cipher

    def encrypt_model(self, configuration: BaseModel) -> dict:
        def encrypt(value: str | None, default: Any) -> str | None:
            if public_default(value, default):
                return value
            if self._cipher is None:
                raise ValueError("Private resource configuration requires encryption")
            return self._cipher.encrypt(value)

        return map_configuration_secrets(configuration, encrypt)

    def decrypt(self, configuration: dict) -> dict:
        return decrypt_values(configuration, self._cipher)

    def public_config(self, category: str, type_key: str, configuration: dict) -> dict:
        """Expose shared settings without handing out reusable encrypted credentials."""
        schema = self._element_registry.get_schema(ResourceCategory(category), type_key)
        try:
            model = schema.model_validate(self.decrypt(configuration), by_name=True)
        except ValidationError:
            raise ValueError(f"Invalid stored configuration for {type_key}") from None
        return map_configuration_secrets(
            model, lambda value, default: value if public_default(value, default) else ""
        )

    def strip_unconfigured_secrets(self, category: str, type_key: str, configuration: dict) -> dict:
        """Caller-editable credentials, including nested fields, never inherit shared secrets."""
        configurable, sensitive = self.scan_schema_hints(category, type_key)
        stripped = dict(configuration)
        if configurable:
            public = self.public_config(category, type_key, configuration)
            for name in configurable:
                if name in sensitive:
                    stripped.pop(name, None)
                elif name in public:
                    stripped[name] = public[name]
        return stripped

    def scan_schema_hints(self, category: str, type_key: str) -> tuple[set[str], set[str]]:
        schema = self._schema(category, type_key)
        if schema is None:
            return set(), set()
        configurable = {
            name
            for name, field in schema.model_fields.items()
            if field_hints(field).get("read_only", {}).get("read_only") is False
        }
        return configurable, sensitive_fields(schema)

    def canonical_fields(self, category: str, type_key: str, configuration: dict) -> dict:
        """Accept schema field aliases while persisting one unambiguous field name."""
        schema = self._element_registry.get_schema(ResourceCategory(category), type_key)
        aliases = {}
        for name, field in schema.model_fields.items():
            candidates = (
                field.validation_alias.choices
                if isinstance(field.validation_alias, AliasChoices)
                else (field.validation_alias,)
            )
            aliases.update(
                {
                    alias: name
                    for alias in (name, field.alias, *candidates)
                    if isinstance(alias, str)
                }
            )
        result = {}
        for key, value in configuration.items():
            name = aliases.get(key, key)
            if name in result:
                raise ValueError("Ambiguous configuration field aliases")
            result[name] = value
        return result

    def auth_metadata_keys(self, category: str, type_key: str) -> set[str]:
        schema = self._schema(category, type_key)
        return AUTH_METADATA_OVERLAY_FIELDS.intersection(schema.model_fields) if schema else set()

    def find_missing_conditionally_required_secrets(
        self,
        category: str,
        type_key: str,
        resolved_config: BaseModel,
        *,
        candidate_keys: set[str] | None = None,
        require_unconditional: bool = False,
    ) -> list[str]:
        schema = self._schema(category, type_key)
        if schema is None:
            return []
        names = sensitive_fields(schema) if candidate_keys is None else candidate_keys
        missing = []
        for name in sorted(names):
            field = schema.model_fields.get(name)
            if field is None:
                continue
            conditional = field_hints(field).get("conditional", {}).get("visible_when")
            if conditional:
                if not all(
                    getattr(resolved_config, key, None) == value
                    for key, value in conditional.items()
                ):
                    continue
            elif not require_unconditional:
                continue
            if not getattr(resolved_config, name, None):
                missing.append(name)
        return missing

    def _schema(self, category: str, type_key: str) -> type[BaseModel] | None:
        try:
            return self._element_registry.get_schema(ResourceCategory(category), type_key)
        except KeyError:
            return None
