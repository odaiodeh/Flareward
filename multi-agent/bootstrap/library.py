"""Own the existing library's synchronous stores while reusing its resolution services."""

import asyncio
from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass

from mas.application.elements.catalog.card_service import ElementCardService
from mas.application.elements.catalog.element_registry import ElementRegistry
from mas.application.elements.construction.secrets import ConfigurationSecrets
from mas.blueprints.authoring import BlueprintAuthoringService
from mas.blueprints.contracts import BlueprintResolutionSource
from mas.blueprints.inspection import BlueprintInspectionService
from mas.blueprints.queries import BlueprintQueryService
from mas.blueprints.resolution import BlueprintImportSource
from mas.blueprints.resolver import BlueprintResolver
from mas.blueprints.schema import blueprint_schemas
from mas.core.async_work import await_owned
from mas.graph.analysis import BlueprintGraphAnalysisService
from mas.graph.validation.service import GraphValidationService
from mas.resources.authoring import ResourceAuthoringService
from mas.resources.builtin_aware_service import BuiltinAwareResourceService
from mas.resources.field_encryption import ResourceFieldEncryption
from mas.resources.inspection import ResourceInspection
from mas.resources.registry import ResourcesRegistry
from mas.resources.service import CoreResourceService
from mas.validation.service import ElementValidationService
from outbound.crypto import FieldCipher
from outbound.mongo.blueprint_authoring_repository import MongoBlueprintAuthoringRepository
from outbound.mongo.blueprint_resolution import StoredBlueprintResolution
from outbound.mongo.blueprint_usage import MongoBlueprintUsage
from outbound.mongo.builtin_configuration_repository import MongoBuiltinConfigurationRepository
from outbound.mongo.builtin_resource_descriptor_repository import (
    MongoBuiltinResourceDescriptorRepository,
)
from outbound.mongo.builtin_user_config_repository import MongoBuiltinUserConfigRepository
from outbound.mongo.resource_authoring_repository import MongoResourceAuthoringRepository
from outbound.mongo.resource_inspection import StoredResourceInspection
from outbound.mongo.resource_repository import MongoResourceRepository
from pymongo import MongoClient
from pymongo.asynchronous.database import AsyncDatabase

from bootstrap.credentials import receiver_auth
from config.platform_settings import PlatformSettings
from config.receiver_settings import CredentialBackend


@dataclass(frozen=True)
class LibraryServices:
    source: BlueprintImportSource
    authoring: BlueprintAuthoringService
    resources: ResourceAuthoringService
    inspection: ResourceInspection
    blueprint_inspection: BlueprintInspectionService
    graph_analysis: BlueprintGraphAnalysisService
    blueprint_queries: BlueprintQueryService
    resolution: BlueprintResolutionSource


@asynccontextmanager
async def compose_library(
    settings: PlatformSettings,
    elements: ElementRegistry,
    database: AsyncDatabase,
    configuration: ConfigurationSecrets,
) -> AsyncIterator[LibraryServices]:
    async with AsyncExitStack() as owned:
        auth = (
            await owned.enter_async_context(receiver_auth(settings))
            if settings.credentials != CredentialBackend.DISABLED
            else None
        )
        client: MongoClient | None = None

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
                StoredResourceInspection(resource_service),
                BlueprintInspectionService(
                    authoring,
                    resolution,
                    elements,
                    configuration,
                    auth,
                ),
                BlueprintGraphAnalysisService(
                    authoring, resolution, elements, GraphValidationService(elements)
                ),
                BlueprintQueryService(authoring, resolution),
                resolution,
            )
        finally:
            if client is not None:
                await await_owned(asyncio.to_thread(client.close))
