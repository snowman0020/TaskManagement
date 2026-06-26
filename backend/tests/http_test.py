"""Full HTTP integration test against the FastAPI app (mongomock backend)."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import httpx
from mongomock_motor import AsyncMongoMockClient

import app.database as database
from app.services.seed import seed_defaults


async def main():
    client = AsyncMongoMockClient()
    database.mongo.client = client
    database.mongo.db = client["taskmanagement_http_test"]
    await seed_defaults()

    from app.main import app

    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
        # health
        assert (await c.get("/api/health")).json()["status"] == "ok"

        # login as seeded admin
        r = await c.post(
            "/api/auth/login",
            data={"username": "admin", "password": "admin1234"},
        )
        assert r.status_code == 200, r.text
        token = r.json()["access_token"]
        assert r.json()["user"]["role"] == "admin"
        h = {"Authorization": f"Bearer {token}"}
        print("✓ login as admin")

        # bad password rejected
        assert (await c.post("/api/auth/login", data={"username": "admin", "password": "x"})).status_code == 401
        # unauthenticated request rejected
        assert (await c.get("/api/tasks")).status_code == 401
        print("✓ auth guards (bad password 401, no-token 401)")

        # create two tasks -> running numbers
        t1 = (await c.post("/api/tasks", json={"title": "First task", "priority": "high"}, headers=h)).json()
        t2 = (await c.post("/api/tasks", json={"title": "Second task"}, headers=h)).json()
        assert t1["task_number"] == "TASK-1", t1
        assert t2["task_number"] == "TASK-2", t2
        assert t1["status"] == "TODO"
        print(f"✓ create tasks with running numbers: {t1['task_number']}, {t2['task_number']}")

        # newly created task sorts to the TOP of its column (smaller order)
        assert t2["order"] < t1["order"], (t1["order"], t2["order"])
        print(f"✓ new task placed at top of column (order {t2['order']} < {t1['order']})")

        # board grouped by status
        board = (await c.get("/api/tasks/board", headers=h)).json()
        assert set(board["tasks"].keys()) >= {"TODO", "InProgress", "QA", "Done"}
        assert len(board["tasks"]["TODO"]) == 2
        # board respects order: t2 (top) before t1
        assert [t["id"] for t in board["tasks"]["TODO"]] == [t2["id"], t1["id"]]
        print("✓ board groups tasks by status column, ordered top-first")

        # unknown status rejected (data integrity)
        bad = await c.post("/api/tasks", json={"title": "x", "status": "Nope"}, headers=h)
        assert bad.status_code == 400, bad.status_code
        print("✓ create rejects unknown status (400)")

        # move TASK-1 through InProgress -> Done: started_at then done_at
        prog = (await c.patch(f"/api/tasks/{t1['id']}/move",
                              json={"status": "InProgress", "order": 0}, headers=h)).json()
        assert prog["started_at"] is not None and prog["done_at"] is None
        moved = (await c.patch(f"/api/tasks/{t1['id']}/move",
                               json={"status": "Done", "order": 0}, headers=h)).json()
        assert moved["status"] == "Done"
        assert moved["started_at"] is not None and moved["done_at"] is not None
        print("✓ leadtime timestamps: started_at on InProgress, done_at on Done")

        # task created directly in Done gets done_at (counted in metrics)
        td = (await c.post("/api/tasks", json={"title": "Born done", "status": "Done"}, headers=h)).json()
        assert td["done_at"] is not None, td
        print("✓ task created directly in Done is stamped done_at")

        # bulk reorder endpoint
        rr = await c.patch(
            "/api/tasks/reorder/bulk",
            json={"items": [{"id": t2["id"], "status": "InProgress", "order": 0}]},
            headers=h,
        )
        assert rr.json()["updated"] == 1
        print("✓ bulk reorder persists drag drops")

        # generate sprints (non-Monday start snaps forward to Monday)
        gen = await c.post(
            "/api/sprints/generate",
            json={"start_date": "2026-06-29", "count": 3, "weeks": 2},
            headers=h,
        )
        assert gen.json()["created"] == 3, gen.text
        # re-generating extends the series instead of silently skipping
        gen2 = await c.post(
            "/api/sprints/generate",
            json={"start_date": "2026-08-10", "count": 2, "weeks": 2},
            headers=h,
        )
        assert gen2.json()["created"] == 2, gen2.text
        assert gen2.json()["sprints"][0]["name"] == "Sprint 4"
        print("✓ generate sprints (2-week Mon-Fri) + re-generate extends to Sprint 4/5")

        # dashboard overview
        ov = (await c.get("/api/dashboard/overview", headers=h)).json()
        assert ov["total_tasks"] == 3
        assert ov["done_tasks"] == 2
        assert ov["leadtime_hours"]["samples"] == 2
        print(f"✓ dashboard: {ov['done_tasks']}/{ov['total_tasks']} done, "
              f"completion {ov['completion_rate']}%, leadtime samples={ov['leadtime_hours']['samples']}")

        # role enforcement: member created, member cannot create users
        await c.post("/api/users", json={
            "username": "member1", "email": "m@e.com", "password": "secret1", "role": "member",
        }, headers=h)
        ml = await c.post("/api/auth/login", data={"username": "member1", "password": "secret1"})
        mh = {"Authorization": f"Bearer {ml.json()['access_token']}"}
        forbidden = await c.post("/api/users", json={
            "username": "x", "email": "x@e.com", "password": "secret1",
        }, headers=mh)
        assert forbidden.status_code == 403, forbidden.status_code
        # member CAN create tasks
        assert (await c.post("/api/tasks", json={"title": "by member"}, headers=mh)).status_code == 201
        print("✓ RBAC: member blocked from admin-only create-user, allowed to create tasks")

        # viewer is strictly read-only
        await c.post("/api/users", json={
            "username": "viewer1", "email": "v@e.com", "password": "secret1", "role": "viewer",
        }, headers=h)
        vl = await c.post("/api/auth/login", data={"username": "viewer1", "password": "secret1"})
        vh = {"Authorization": f"Bearer {vl.json()['access_token']}"}
        assert (await c.get("/api/tasks/board", headers=vh)).status_code == 200  # can read
        assert (await c.post("/api/tasks", json={"title": "nope"}, headers=vh)).status_code == 403
        assert (await c.patch(f"/api/tasks/{t1['id']}/move",
                              json={"status": "QA", "order": 0}, headers=vh)).status_code == 403
        assert (await c.delete(f"/api/tasks/{t1['id']}", headers=vh)).status_code == 403
        print("✓ RBAC: viewer can read board but blocked (403) from create/move/delete")

        # admin cannot demote/lock out the last admin
        me = (await c.get("/api/auth/me", headers=h)).json()
        lock = await c.patch(f"/api/users/{me['id']}", json={"role": "viewer"}, headers=h)
        assert lock.status_code == 400, lock.status_code
        # malformed id -> 400 (not 500)
        assert (await c.patch("/api/users/not-an-id", json={"role": "member"}, headers=h)).status_code == 400
        print("✓ guards: last-admin lockout blocked (400), malformed id -> 400")

    print("\nALL HTTP INTEGRATION CHECKS PASSED")


asyncio.run(main())
