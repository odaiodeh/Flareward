"""ASGI factory: uvicorn flareward.bootstrap.asgi:create_app --factory."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from flareward.api.app import create_app as create_http_app
from flareward.bootstrap.platform import compose_platform
from flareward.bootstrap.settings.platform_settings import PlatformSettings


def create_app() -> FastAPI:
    settings = PlatformSettings()
    app = create_http_app(services_factory=lambda: compose_platform(settings))
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.frontend_url],
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
    )
    return app
