"""Native async identity-session authentication compatible with existing signed cookies."""

import hashlib
import hmac
import json
from collections.abc import Mapping
from typing import Protocol

import httpx
from fastapi import HTTPException, Request
from global_utils.redis.session_model import UserSessionData
from itsdangerous import BadSignature, URLSafeTimedSerializer

from flareward.services.identity.domain import Identity


class SessionReader(Protocol):
    async def hgetall(self, name: str) -> Mapping[str, str]: ...


class DevelopmentAuthenticator:
    def __init__(self, username: str) -> None:
        if not username.strip():
            raise ValueError("Development authentication requires an explicit username")
        self._identity = Identity.user(username)

    async def __call__(self, request: Request) -> Identity:
        request.state.authenticated_user = self._identity.id
        return self._identity.model_copy(deep=True)


class SessionAuthenticator:
    def __init__(
        self,
        sessions: SessionReader,
        http: httpx.AsyncClient,
        *,
        secret_key: str,
        identity_url: str,
        cookie_name: str = "session",
        cookie_max_age: int = 86400,
        internal_token: str = "",
    ) -> None:
        if not secret_key:
            raise ValueError("Session authentication requires the shared cookie secret")
        self._sessions = sessions
        self._http = http
        self._identity_url = identity_url.rstrip("/")
        self._cookie_name = cookie_name
        self._max_age = cookie_max_age
        self._internal_token = internal_token
        self._serializer = URLSafeTimedSerializer(
            secret_key,
            salt="cookie-session",
            serializer=json,
            signer_kwargs={"key_derivation": "hmac", "digest_method": hashlib.sha1},
        )

    async def __call__(self, request: Request) -> Identity:
        user = await self._user(request)
        request.state.authenticated_user = user
        team_id = request.query_params.get("teamId", "")
        if not team_id and request.method in {"POST", "PUT", "PATCH"}:
            if request.headers.get("content-type", "").split(";")[0] == "application/json":
                body = await request.json()
                if isinstance(body, dict):
                    team_id = body.get("teamId", "")
        if not team_id:
            return Identity.user(user)
        if not self._identity_url:
            raise HTTPException(
                status_code=403, detail="Team membership provider is not configured"
            )
        response = await self._http.get(
            f"{self._identity_url}/api/teams/teams.list",
            params={"userId": user},
        )
        response.raise_for_status()
        teams = response.json().get("teams", [])
        for team in teams:
            if str(team.get("team_id")) == team_id:
                return Identity.team(team_id, str(team.get("name") or team_id))
        raise HTTPException(status_code=403, detail="Access denied: not a member of this team")

    async def _user(self, request: Request) -> str:
        cookie = request.cookies.get(self._cookie_name)
        if cookie:
            try:
                decoded = self._serializer.loads(cookie, max_age=self._max_age)
            except BadSignature:
                raise HTTPException(status_code=401, detail="Invalid session cookie") from None
            session_id = decoded.get("session_id") if isinstance(decoded, dict) else None
            if session_id:
                raw = await self._sessions.hgetall(f"identity:session:{session_id}")
                session = UserSessionData.from_redis_hash(raw)
                if session and session.has_auth_credentials() and not session.is_session_expired():
                    return session.username
            raise HTTPException(status_code=401, detail="Session expired or not authenticated")
        token = request.headers.get("X-Internal-Token", "")
        user = request.headers.get("X-Authenticated-User", "").strip()
        if self._internal_token and user and hmac.compare_digest(token, self._internal_token):
            return user
        raise HTTPException(status_code=401, detail="Not authenticated")
