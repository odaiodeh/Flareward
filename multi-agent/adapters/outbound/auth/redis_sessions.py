"""Adapt Redis's bytes/text transport to the authenticator's narrow text reader."""

from redis.asyncio import Redis


class RedisSessionReader:
    def __init__(self, client: Redis) -> None:
        self._client = client

    async def hgetall(self, name: str) -> dict[str, str]:
        values = await self._client.hgetall(name)
        return {
            key.decode() if isinstance(key, bytes) else key: value.decode()
            if isinstance(value, bytes)
            else value
            for key, value in values.items()
        }
