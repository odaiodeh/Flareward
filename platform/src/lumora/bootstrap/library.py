"""Own the existing library's synchronous stores while reusing its resolution services."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass
from importlib import import_module
from typing import Any

from pymongo import MongoClient
from pymongo.asynchronous.database import AsyncDatabase

from lumora.async_work import await_owned
from lumora.bootstrap.credentials import receiver_auth
from lumora.bootstrap.plugins import installed_plugins
from lumora.bootstrap.settings.platform_settings import PlatformSettings
from lumora.bootstrap.settings.receiver_settings import CredentialBackend
from lumora.elements.catalog.card_service import ElementCardService
from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.elements.validation_services.service import ElementValidationService
from lumora.programs.graph.analysis import BlueprintGraphAnalysisService
from lumora.programs.graph.validation.service import GraphValidationService
from lumora.programs.templates.adapters.mongo.blueprint_authoring_repository import (
    MongoBlueprintAuthoringRepository,
)
from lumora.programs.templates.adapters.mongo.blueprint_resolution import (
    StoredBlueprintResolution,
)
from lumora.programs.templates.adapters.mongo.blueprint_usage import MongoBlueprintUsage
from lumora.programs.templates.authoring import BlueprintAuthoringService
from lumora.programs.templates.contracts import BlueprintResolutionSource
from lumora.programs.templates.inspection import BlueprintInspectionService
from lumora.programs.templates.queries import BlueprintQueryService
from lumora.programs.templates.resolution import BlueprintImportSource
from lumora.programs.templates.resolver import BlueprintResolver
from lumora.programs.templates.schema import blueprint_schemas
from lumora.resources.adapters.mongo.builtin_administration import MongoBuiltinAdministration
from lumora.resources.adapters.mongo.builtin_configuration_repository import (
    MongoBuiltinConfigurationRepository,
)
from lumora.resources.adapters.mongo.builtin_resource_descriptor_repository import (
    MongoBuiltinResourceDescriptorRepository,
)
from lumora.resources.adapters.mongo.builtin_user_config_repository import (
    MongoBuiltinUserConfigRepository,
)
from lumora.resources.adapters.mongo.resource_authoring_repository import (
    MongoResourceAuthoringRepository,
)
from lumora.resources.adapters.mongo.resource_inspection import StoredResourceProbe
from lumora.resources.adapters.mongo.resource_repository import MongoResourceRepository
from lumora.resources.authoring import ResourceAuthoringService
from lumora.resources.builtin_aware_service import BuiltinAwareResourceService
from lumora.resources.builtins import BuiltinRepository
from lumora.resources.configuration import ResourceConfiguration
from lumora.resources.field_encryption import ResourceFieldEncryption
from lumora.resources.inspection import ResourceInspectionService
from lumora.resources.registry import ResourcesRegistry
from lumora.resources.service import CoreResourceService
from lumora.services.access.administrators import AdministratorAccess
from lumora.services.auth.adapters.crypto import FieldCipher


@dataclass(frozen=True)
class LibraryServices:
    source: BlueprintImportSource
    authoring: BlueprintAuthoringService
    resources: ResourceAuthoringService
    inspection: ResourceInspectionService
    blueprint_inspection: BlueprintInspectionService
    graph_analysis: BlueprintGraphAnalysisService
    blueprint_queries: BlueprintQueryService
    resolution: BlueprintResolutionSource
    builtin_repository: BuiltinRepository
    resource_configuration: ResourceConfiguration


@asynccontextmanager
async def compose_library(
    settings: PlatformSettings,
    elements: ElementRegistry,
    database: AsyncDatabase[dict[str, Any]],
    configuration: ConfigurationSecrets,
    administrators: AdministratorAccess,
) -> AsyncIterator[LibraryServices]:
    async with AsyncExitStack() as owned:
        auth = (
            await owned.enter_async_context(receiver_auth(settings))
            if settings.credentials != CredentialBackend.DISABLED
            else None
        )
        client: MongoClient[dict[str, Any]] | None = None

        def initialize() -> tuple[ResourceFieldEncryption, BuiltinAwareResourceService]:
            nonlocal client
            client = MongoClient(
                settings.mongo_uri.get_secret_value(), serverSelectionTimeoutMS=5000
            )
            client.admin.command("ping")
            database = client[settings.mongo_database]
            blueprints = MongoBlueprintUsage(database[settings.blueprints_collection])
            resources = MongoResourceRepository(
                coll_name=settings.resources_collection, database=database
            )
            descriptors = MongoBuiltinResourceDescriptorRepository(
                coll_name=settings.builtin_descriptors_collection,
                resources_coll_name=settings.resources_collection,
                database=database,
            )
            overlays = MongoBuiltinUserConfigRepository(
                coll_name=settings.builtin_user_configs_collection, database=database
            )
            key = settings.credential_encryption_key.get_secret_value()
            cipher = FieldCipher(key) if key else None
            registry = ResourcesRegistry(resources, blueprints, cipher)
            fields = ResourceFieldEncryption(elements, cipher)
            service = BuiltinAwareResourceService(
                CoreResourceService(
                    registry,
                    elements,
                    fields,
                    ElementValidationService(elements),
                    ElementCardService(elements),
                    auth,
                ),
                descriptor_repo=descriptors,
                builtin_user_config_repo=overlays,
            )
            return fields, service

        try:
            fields, resource_service = await await_owned(asyncio.to_thread(initialize))
            repository = MongoBlueprintAuthoringRepository(database[settings.blueprints_collection])
            await repository.initialize()
            resource_repository = MongoResourceAuthoringRepository(
                database,
                resources=settings.resources_collection,
                descriptors=settings.builtin_descriptors_collection,
                blueprints=settings.blueprints_collection,
            )
            await resource_repository.initialize()
            overlay_repository = MongoBuiltinConfigurationRepository(
                database[settings.builtin_user_configs_collection]
            )
            await overlay_repository.initialize()
            schemas = blueprint_schemas(elements)
            authoring = BlueprintAuthoringService(repository, schemas.draft, configuration)
            resolution = StoredBlueprintResolution(
                BlueprintResolver(resource_service, spec_schema=schemas.resolved), schemas.draft
            )
            yield LibraryServices(
                BlueprintImportSource(authoring, resolution),
                authoring,
                ResourceAuthoringService(resource_repository, elements, fields, overlay_repository),
                ResourceInspectionService(
                    StoredResourceProbe(resource_service), administrators, resource_repository
                ),
                BlueprintInspectionService(
                    authoring,
                    resolution,
                    elements,
                    configuration,
                    auth,
                ),
                BlueprintGraphAnalysisService(
                    authoring,
                    resolution,
                    elements,
                    GraphValidationService(
                        elements,
                        extra_validators=tuple(
                            getattr(
                                import_module(reference.split(":")[0]), reference.split(":")[1]
                            )()
                            for plugin in installed_plugins(settings.plugins)
                            for reference in plugin.graph_validators
                        ),
                    ),
                ),
                BlueprintQueryService(authoring, resolution),
                resolution,
                MongoBuiltinAdministration(
                    database,
                    resources=settings.resources_collection,
                    descriptors=settings.builtin_descriptors_collection,
                    blueprints=settings.blueprints_collection,
                    overlays=settings.builtin_user_configs_collection,
                ),
                ResourceConfiguration(elements, fields),
            )
        finally:
            if client is not None:
                await await_owned(asyncio.to_thread(client.close))
