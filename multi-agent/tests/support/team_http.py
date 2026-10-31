"""Real signed-cookie/team authorization shared by native HTTP integration scenarios."""

from contextlib import AsyncExitStack, asynccontextmanager
from dataclasses import dataclass, replace
from uuid import uuid4

import httpx
from inbound.http_api.app import create_app
from inbound.http_api.authentication import SessionAuthenticator
from mas.application.actions.service import ActionsService
from outbound.redis_client import owned_redis
from pydantic import SecretStr
from redis.asyncio import Redis

from bootstrap.platform import compose_platform
from config.platform_settings import PlatformSettings
from support.identity import authenticated_cookie


@dataclass(frozen=True)
class TeamHTTP:
    team_id: str
    clients: dict[str, httpx.AsyncClient]
    redis: Redis


@asynccontextmanager
async def team_api(
    settings: PlatformSettings, redis_uri: str, *, actions: ActionsService | None = None
):
    team_id, secret = "editing-" + uuid4().hex, uuid4().hex
    settings = settings.model_copy(update={"redis_uri": SecretStr(redis_uri)})
    async with AsyncExitStack() as owned:
        redis = await owned.enter_async_context(owned_redis(redis_uri, decode_responses=True))
        cookies = {
            user: await owned.enter_async_context(authenticated_cookie(redis, user, secret))
            for user in ("alice", "bob", "mallory")
        }

        async def membership(request):
            assert request.url.path == "/api/teams/teams.list"
            teams = (
                [{"team_id": team_id, "name": "Editing team"}]
                if request.url.params["userId"] in ("alice", "bob")
                else []
            )
            return httpx.Response(200, json={"teams": teams})

        identity = await owned.enter_async_context(
            httpx.AsyncClient(transport=httpx.MockTransport(membership))
        )
        authenticate = SessionAuthenticator(
            redis, identity, secret_key=secret, identity_url="http://identity-fixture"
        )

        async def clear_leases():
            keys = [
                key async for key in redis.scan_iter(match=f"mas:collab:editlock:team:{team_id}:*")
            ]
            if keys:
                await redis.delete(*keys)

        owned.push_async_callback(clear_leases)

        @asynccontextmanager
        async def services():
            async with compose_platform(settings) as platform:
                yield replace(
                    platform, authenticate=authenticate, actions=actions or platform.actions
                )

        app = create_app(services_factory=services)
        await owned.enter_async_context(app.router.lifespan_context(app))
        clients = {
            user: await owned.enter_async_context(
                httpx.AsyncClient(
                    transport=httpx.ASGITransport(app),
                    base_url="http://platform",
                    cookies={"session": cookie},
                )
            )
            for user, cookie in cookies.items()
        }
        yield TeamHTTP(team_id, clients, redis)
