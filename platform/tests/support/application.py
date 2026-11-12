"""Application test composition: no HTTP, engine, transport, or database clients."""

from dataclasses import dataclass

from lumora.elements.catalog.element_registry import ElementRegistry
from lumora.elements.construction.secrets import ConfigurationSecrets
from lumora.programs.adapters.memory.program_repository import MemoryProgramRepository
from lumora.programs.registry import CoordinatorRegistry
from lumora.programs.service import ProgramService
from lumora.resources.secrets import ConfigurationSecretStore
from lumora.services.identity.domain import Identity
from support.elements import element_registry
from support.programs import COORDINATORS


@dataclass(frozen=True)
class Application:
    programs: ProgramService
    owner: Identity
    elements: ElementRegistry
    applications: CoordinatorRegistry


def make_application(secret_store: ConfigurationSecretStore | None = None) -> Application:
    elements = element_registry()
    applications = CoordinatorRegistry()
    for registration in COORDINATORS:
        applications.register(registration)
    programs = ProgramService(
        MemoryProgramRepository(),
        applications,
        elements,
        ConfigurationSecrets(elements, secret_store),
    )
    return Application(programs, Identity.user("alice"), elements, applications)
