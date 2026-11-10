"""Native composition with deterministic capabilities and production authentication."""

from functools import partial

from lumora.api.app import create_app as http_app
from lumora.bootstrap.platform import compose_platform
from lumora.bootstrap.settings.platform_settings import PlatformSettings
from support.blueprints import library_elements
from support.elements import ELEMENT_SPECIFICATIONS


def create_app():
    elements = library_elements()
    for specification in ELEMENT_SPECIFICATIONS:
        elements.register_spec_class(specification)
    return http_app(
        services_factory=partial(compose_platform, PlatformSettings(), elements=elements)
    )
