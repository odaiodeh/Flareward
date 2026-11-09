"""Production service/auth composition with deterministic inspection capabilities."""

from functools import partial

from flareward.api.app import create_app as http_app
from flareward.bootstrap.platform import compose_platform
from flareward.bootstrap.settings.platform_settings import PlatformSettings
from support.inspection import inspection_elements


def create_app():
    return http_app(
        services_factory=partial(
            compose_platform, PlatformSettings(), elements=inspection_elements()
        )
    )
