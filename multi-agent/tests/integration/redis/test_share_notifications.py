"""Signed-cookie notifications enforce selected workspace and human identity with actual Mongo."""

import asyncio

from mas.core.identity import Identity
from support.sharing import invitation
from support.team_http import team_api


async def test_native_notifications_preserve_ui_shapes_and_hide_internal_owner_pools(
    secret_settings, redis_uri, mongo_database
):
    async with team_api(secret_settings, redis_uri) as team:
        alice, bob, mallory = (team.clients[user] for user in ("alice", "bob", "mallory"))
        for invite in (
            invitation("personal"),
            invitation("team", sender_identity=Identity.team(team.team_id, "Source team")),
            invitation("incoming-team", recipient_identity=Identity.team(team.team_id)),
        ):
            await mongo_database.shares.insert_one(invite.model_dump(mode="json"))
        personal = await bob.get("/api/shares/shares.list")
        assert personal.status_code == 200
        assert {item["share_id"] for item in personal.json()["invites"]} == {"personal", "team"}
        assert personal.json()["count"] == 2
        assert "internal-owner-pool" not in personal.text
        sent = await alice.get(
            "/api/shares/shares.list", params={"direction": "sent", "teamId": team.team_id}
        )
        assert sent.status_code == 200 and sent.json()["count"] == 1
        assert sent.json()["invites"][0]["sender_display_name"] == "Source team"
        assert (
            await mallory.get("/api/shares/shares.list", params={"teamId": team.team_id})
        ).status_code == 403
        assert (
            await mallory.get("/api/shares/share.get", params={"shareId": "personal"})
        ).status_code == 403
        assert (
            await bob.get("/api/shares/share.get", params={"shareId": "missing"})
        ).status_code == 404
        assert (
            await bob.get("/api/shares/share.get", params={"shareId": "team"})
        ).status_code == 200
        assert (
            await alice.get(
                "/api/shares/share.get", params={"shareId": "team", "teamId": team.team_id}
            )
        ).status_code == 200
        for params in (
            {"limit": 0},
            {"skip": -1},
            {"direction": "private-invalid"},
            {"status": "invalid"},
        ):
            response = await alice.get("/api/shares/shares.list", params=params)
            assert response.status_code == 422
        for user, route in ((alice, "decline"), (bob, "cancel")):
            denied = await user.post("/api/shares/share." + route, json={"shareId": "personal"})
            assert denied.status_code == 403
        results = await asyncio.gather(
            bob.post("/api/shares/share.decline", json={"shareId": "personal"}),
            alice.post("/api/shares/share.cancel", json={"shareId": "personal"}),
        )
        assert sorted(result.status_code for result in results) == [200, 409]
        outcome = (await bob.get("/api/shares/share.get", params={"shareId": "personal"})).json()[
            "status"
        ]
        actor, route = (bob, "decline") if outcome == "declined" else (alice, "cancel")
        assert (
            await actor.post("/api/shares/share." + route, json={"shareId": "personal"})
        ).status_code == 200
        assert (
            await alice.post("/api/shares/share.decline", json={"shareId": "incoming-team"})
        ).status_code == 403
        scoped = await alice.post(
            "/api/shares/share.decline", json={"shareId": "incoming-team", "teamId": team.team_id}
        )
        assert scoped.status_code == 200
        forged = await mallory.post(
            "/api/shares/share.cancel", json={"shareId": "team", "teamId": team.team_id}
        )
        assert forged.status_code == 403
        assert (
            await alice.get("/api/shares/shares.list", headers={"Cookie": ""})
        ).status_code == 401
