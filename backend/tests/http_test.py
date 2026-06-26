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

        # board grouped by status
        board = (await c.get("/api/tasks/board", headers=h)).json()
        assert set(board["tasks"].keys()) >= {"TODO", "InProgress", "QA", "Done"}
        assert len(board["tasks"]["TODO"]) == 2
        print("✓ board groups tasks by status column")

        # drag-and-drop move TASK-1 to Done -> sets started_at + done_at
        moved = (await c.patch(
            f"/api/tasks/{t1['id']}/move",
            json={"status": "Done", "order": 0},
            headers=h,
        )).json()
        assert moved["status"] == "Done"
        assert moved["started_at"] is not None
        assert moved["done_at"] is not None
        print("✓ drag-and-drop move sets leadtime timestamps (started_at + done_at)")

        # bulk reorder endpoint
        rr = await c.patch(
            "/api/tasks/reorder/bulk",
            json={"items": [{"id": t2["id"], "status": "InProgress", "order": 0}]},
            headers=h,
        )
        assert rr.json()["updated"] == 1
        print("✓ bulk reorder persists drag drops")

        # generate sprints
        gen = await c.post(
            "/api/sprints/generate",
            json={"start_date": "2026-06-29", "count": 3, "weeks": 2},
            headers=h,
        )
        assert gen.json()["created"] == 3, gen.text
        print("✓ generate 3 sprints (2-week Mon-Fri)")

        # dashboard overview
        ov = (await c.get("/api/dashboard/overview", headers=h)).json()
        assert ov["total_tasks"] == 2
        assert ov["done_tasks"] == 1
        assert ov["leadtime_hours"]["samples"] == 1
        print(f"✓ dashboard: {ov['done_tasks']}/{ov['total_tasks']} done, "
              f"completion {ov['completion_rate']}%, leadtime samples={ov['leadtime_hours']['samples']}")

        # role enforcement: create a member, member cannot create users
        member = (await c.post("/api/users", json={
            "username": "member1", "email": "m@e.com", "password": "secret1", "role": "member",
        }, headers=h)).json()
        ml = await c.post("/api/auth/login", data={"username": "member1", "password": "secret1"})
        mh = {"Authorization": f"Bearer {ml.json()['access_token']}"}
        forbidden = await c.post("/api/users", json={
            "username": "x", "email": "x@e.com", "password": "secret1",
        }, headers=mh)
        assert forbidden.status_code == 403, forbidden.status_code
        print("✓ RBAC: member blocked (403) from admin-only create-user")

    print("\nALL HTTP INTEGRATION CHECKS PASSED")


asyncio.run(main())
