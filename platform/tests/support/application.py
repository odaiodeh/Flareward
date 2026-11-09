"""Application test composition: no HTTP, engine, transport, or database clients."""

from dataclasses import dataclass

from flareward.elements.catalog.element_registry import ElementRegistry
from flareward.elements.construction.secrets import ConfigurationSecrets
from flareward.programs.adapters.memory.program_repository import MemoryProgramRepository
from flareward.programs.registry import ApplicationRegistry
from flareward.programs.service import ProgramService
from flareward.resources.secrets import ConfigurationSecretStore
from flareward.services.identity.domain import Identity
from support.elements import element_registry
from support.programs import APPLICATION_PROGRAMS


@dataclass(frozen=True)
class Application:
    programs: ProgramService
    owner: Identity
    elements: ElementRegistry
    applications: ApplicationRegistry


def make_application(secret_store: ConfigurationSecretStore | None = None) -> Application:
    elements = element_registry()
    applications = ApplicationRegistry()
    for registration in APPLICATION_PROGRAMS:
        applications.register(registration)
    programs = ProgramService(
        MemoryProgramRepository(),
        applications,
        elements,
        ConfigurationSecrets(elements, secret_store),
    )
    return Application(programs, Identity.user("alice"), elements, applications)
