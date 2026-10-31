"""Signed-cookie and team scope behavior without Flask or synchronous HTTP clients."""

import time

import httpx
from fastapi import FastAPI, Request
from inbound.http_api.authentication import SessionAuthenticator
from support.identity import session_cookie as cookie


class Sessions:
    def __init__(self):
        self.values = {}

    async def hgetall(self, key):
        return self.values.get(key, {})


async def client_for(sessions, *, internal_token=""):
    transport = httpx.MockTransport(
        lambda request: httpx.Response(
            200,
            json={
                "teams": [{"team_id": "engineering", "name": "Engineering"}],
            },
        )
    )
    http = httpx.AsyncClient(transport=transport)
    authenticate = SessionAuthenticator(
        sessions,
        http,
        secret_key="test-secret",
        identity_url="http://identity",
        internal_token=internal_token,
    )
    app = FastAPI()

    @app.get("/identity")
    @app.post("/identity")
    async def identity(request: Request):
        result = await authenticate(request)
        return {
            "identity": result.model_dump(mode="json"),
            "credential_user": request.state.authenticated_user,
        }

    return http, httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://platform")


async def test_signed_cookie_resolves_server_session_and_team_without_changing_acting_human():
    sessions = Sessions()
    sessions.values["identity:session:valid"] = {
        "username": "alice",
        "access_token": "test-token",
        "session_expires_at": time.time() + 60,
    }
    http, client = await client_for(sessions)
    async with http, client:
        personal = await client.get("/identity", headers={"Cookie": f"session={cookie('valid')}"})
        assert personal.json()["identity"]["id"] == "alice"
        team = await client.get(
            "/identity?teamId=engineering", headers={"Cookie": f"session={cookie('valid')}"}
        )
        assert team.json()["identity"] == {
            "type": "team",
            "id": "engineering",
            "display_name": "Engineering",
        }
        assert team.json()["credential_user"] == "alice"
        denied = await client.get(
            "/identity?teamId=other", headers={"Cookie": f"session={cookie('valid')}"}
        )
        assert denied.status_code == 403


async def test_editor_body_team_selection_uses_membership_and_preserves_authenticated_user():
    sessions = Sessions()
    sessions.values["identity:session:valid"] = {
        "username": "alice",
        "access_token": "test-token",
        "session_expires_at": time.time() + 60,
    }
    http, client = await client_for(sessions)
    async with http, client:
        client.cookies.set("session", cookie("valid"))
        team = await client.post("/identity", json={"teamId": "engineering", "userId": "other"})
        assert team.json()["identity"]["id"] == "engineering"
        assert team.json()["credential_user"] == "alice"
        assert (
            await client.post("/identity", json={"teamId": "not-a-members-team"})
        ).status_code == 403
        personal = await client.post("/identity", json={"userId": "other"})
        assert personal.json()["identity"]["id"] == "alice"


async def test_missing_forged_and_expired_sessions_are_refused():
    sessions = Sessions()
    sessions.values["identity:session:expired"] = {
        "username": "alice",
        "access_token": "test-token",
        "session_expires_at": time.time() - 1,
    }
    http, client = await client_for(sessions)
    async with http, client:
        assert (await client.get("/identity")).status_code == 401
        assert (
            await client.get("/identity", headers={"Cookie": f"session={cookie('valid', 'wrong')}"})
        ).status_code == 401
        assert (
            await client.get("/identity", headers={"Cookie": f"session={cookie('expired')}"})
        ).status_code == 401
        assert (
            await client.get("/identity", headers={"X-Authenticated-User": "alice"})
        ).status_code == 401


async def test_internal_identity_requires_configured_shared_token():
    http, client = await client_for(Sessions(), internal_token="internal-test")
    async with http, client:
        headers = {"X-Authenticated-User": "alice", "X-Internal-Token": "internal-test"}
        assert (await client.get("/identity", headers=headers)).json()["identity"]["id"] == "alice"
