"""Administrator authorization and schema-validated settings edits."""

from datetime import UTC, datetime

from pydantic import JsonValue, ValidationError

from flareward.services.access.administrators import AdministratorAccess
from flareward.services.administration.contracts import (
    SettingsConflict,
    SettingsRecord,
    SettingsRepository,
    SettingsSection,
)
from flareward.services.administration.views import (
    CategoryView,
    ConfigurationView,
    FieldKind,
    FieldView,
    SectionView,
)
from flareward.services.identity.domain import Identity


class ConfigurationService:
    def __init__(
        self,
        repository: SettingsRepository,
        administrators: AdministratorAccess,
        sections: tuple[SettingsSection, ...],
    ) -> None:
        self._repository, self._administrators = repository, administrators
        self._sections = {section.key: section for section in sections}
        if len(self._sections) != len(sections):
            raise ValueError("Settings sections require unique identities")

    async def allowed(self, user: Identity) -> bool:
        return await self._administrators.allowed(user)

    async def _authorize(self, user: Identity) -> None:
        if not await self.allowed(user):
            raise PermissionError("Administrator access is required")

    async def read(self, user: Identity) -> ConfigurationView:
        await self._authorize(user)
        categories = []
        for section in self._sections.values():
            record = await self._repository.get(section.key)
            values = record.value if record else section.defaults
            properties = section.schema.model_json_schema()["properties"]
            fields = []
            for name, metadata in properties.items():
                kind = metadata.get("type")
                field_type = {
                    "array": FieldKind.STRING_LIST,
                    "object": FieldKind.JSON,
                    "integer": FieldKind.NUMBER,
                }.get(kind, kind)
                fields.append(
                    FieldView(
                        key=name,
                        label=metadata.get("title", name),
                        field_type=field_type,
                        description=metadata.get("description", ""),
                        default=section.defaults.get(name),
                        value=values.get(name),
                    )
                )
            categories.append(
                CategoryView(
                    key=section.category,
                    title=section.title,
                    sections=(
                        SectionView(
                            key=section.key,
                            title=section.title,
                            fields=tuple(fields),
                            updated_at=record.updated_at if record else None,
                            revision=record.revision if record else 0,
                        ),
                    ),
                )
            )
        return ConfigurationView(categories=tuple(categories))

    async def update(
        self, key: str, values: dict[str, JsonValue], expected_revision: int, user: Identity
    ) -> SettingsRecord:
        await self._authorize(user)
        section = self._sections.get(key)
        if section is None:
            raise KeyError("Unknown configuration section")
        try:
            value = section.schema.model_validate(values).model_dump(mode="json")
        except ValidationError:
            raise ValueError("Configuration violates its section schema") from None
        record = SettingsRecord(
            key=key, value=value, revision=expected_revision + 1, updated_at=datetime.now(UTC)
        )
        if not await self._repository.replace(record, expected_revision):
            raise SettingsConflict("Configuration changed; reload before saving")
        return record
