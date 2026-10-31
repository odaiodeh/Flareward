"""Production HTTP assembly with an explicit test identity boundary."""

from contextlib import asynccontextmanager
from dataclasses import replace

import httpx
from inbound.http_api.app import create_app

from bootstrap.platform import compose_platform
from support.blueprints import library_elements


@asynccontextmanager
async def library_api(settings, owner, *, elements=None):
    async def authenticate(request):
        request.state.authenticated_user = "human"
        return owner

    @asynccontextmanager
    async def services():
        async with compose_platform(settings, elements=elements or library_elements()) as platform:
            yield replace(platform, authenticate=authenticate)

    app = create_app(services_factory=services)
    async with app.router.lifespan_context(app):
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app), base_url="http://platform"
        ) as http:
            yield http
