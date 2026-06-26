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

        # assignee filter on the board (by-user + unassigned sentinel)
        me = (await c.get("/api/auth/me", headers=h)).json()
        mine = (await c.post("/api/tasks", json={"title": "mine", "assignee_id": me["id"]}, headers=h)).json()
        b_me = (await c.get(f"/api/tasks/board?assignee_id={me['id']}", headers=h)).json()
        me_tasks = [t for col in b_me["tasks"].values() for t in col]
        assert mine["id"] in [t["id"] for t in me_tasks]
        assert all(t.get("assignee_id") == me["id"] for t in me_tasks)
        b_none = (await c.get("/api/tasks/board?assignee_id=none", headers=h)).json()
        none_tasks = [t for col in b_none["tasks"].values() for t in col]
        assert mine["id"] not in [t["id"] for t in none_tasks]
        assert all(not t.get("assignee_id") for t in none_tasks)
        print("✓ board assignee filter: by-user returns only theirs, 'none' returns unassigned")

        # sprint manday: create / patch / generate-default persist; negative rejected
        sp = (await c.post("/api/sprints", json={
            "name": "Manday Sprint", "start_date": "2026-09-07", "weeks": 2, "manday": 18.5,
        }, headers=h)).json()
        assert sp["manday"] == 18.5, sp
        upd = (await c.patch(f"/api/sprints/{sp['id']}", json={"manday": 20}, headers=h)).json()
        assert upd["manday"] == 20
        gens = await c.post("/api/sprints/generate", json={
            "start_date": "2026-10-05", "count": 2, "weeks": 2, "name_prefix": "Cap", "manday": 12,
        }, headers=h)
        assert all(s["manday"] == 12 for s in gens.json()["sprints"]), gens.text
        bad = await c.post("/api/sprints", json={
            "name": "Bad Manday", "start_date": "2026-11-02", "manday": -5,
        }, headers=h)
        assert bad.status_code == 422, bad.status_code
        print("✓ sprint manday: create/patch/generate persist, negative rejected (422)")

        # backlog view: sprint_id=none returns only sprint-less tasks
        sprint_list = (await c.get("/api/sprints", headers=h)).json()
        sid = sprint_list[0]["id"]
        in_sprint = (await c.post("/api/tasks", json={"title": "in sprint", "sprint_id": sid}, headers=h)).json()
        backlog_task = (await c.post("/api/tasks", json={"title": "in backlog"}, headers=h)).json()
        bl = (await c.get("/api/tasks/board?sprint_id=none", headers=h)).json()
        bl_tasks = [t for col in bl["tasks"].values() for t in col]
        assert backlog_task["id"] in [t["id"] for t in bl_tasks]
        assert in_sprint["id"] not in [t["id"] for t in bl_tasks]
        assert all(not t.get("sprint_id") for t in bl_tasks)
        print("✓ board backlog filter (sprint_id=none) returns only sprint-less tasks")

        # task move history: t1 was moved TODO->InProgress->Done earlier
        hist = (await c.get(f"/api/tasks/{t1['id']}/history", headers=h)).json()
        assert len(hist) == 2, hist
        assert hist[0]["from_status"] == "InProgress" and hist[0]["to_status"] == "Done"
        assert hist[1]["from_status"] == "TODO" and hist[1]["to_status"] == "InProgress"
        assert all(e["username"] == "admin" for e in hist)
        # a same-column reorder records nothing new
        await c.patch("/api/tasks/reorder/bulk",
                      json={"items": [{"id": t1["id"], "status": "Done", "order": 1}]}, headers=h)
        assert len((await c.get(f"/api/tasks/{t1['id']}/history", headers=h)).json()) == 2
        print("✓ task move history: status changes logged newest-first, same-column reorder ignored")

        # complete sprint: deletes only THIS sprint's done tasks, marks it completed
        csp = (await c.post("/api/sprints", json={"name": "Done Sprint", "start_date": "2026-12-07"}, headers=h)).json()
        csid = csp["id"]
        done_in = (await c.post("/api/tasks", json={"title": "done in sprint", "status": "Done", "sprint_id": csid}, headers=h)).json()
        todo_in = (await c.post("/api/tasks", json={"title": "todo in sprint", "sprint_id": csid}, headers=h)).json()
        done_backlog = (await c.post("/api/tasks", json={"title": "done backlog", "status": "Done"}, headers=h)).json()
        comp = (await c.post(f"/api/sprints/{csid}/complete", headers=h)).json()
        assert comp["deleted"] == 1, comp
        assert comp["sprint"]["status"] == "completed", comp
        assert (await c.get(f"/api/tasks/{done_in['id']}", headers=h)).status_code == 404
        assert (await c.get(f"/api/tasks/{todo_in['id']}", headers=h)).status_code == 200
        assert (await c.get(f"/api/tasks/{done_backlog['id']}", headers=h)).status_code == 200
        print("✓ complete sprint: deletes only the sprint's done tasks, marks it completed")

        # status columns: drag-reorder persists, then restore original order
        cols = (await c.get("/api/status-columns", headers=h)).json()
        n = len(cols)
        rev = [{"id": col["id"], "order": n - 1 - i} for i, col in enumerate(cols)]
        assert (await c.patch("/api/status-columns/reorder", json={"items": rev}, headers=h)).json()["updated"] == n
        cols2 = (await c.get("/api/status-columns", headers=h)).json()
        assert [col["key"] for col in cols2] == [col["key"] for col in reversed(cols)]
        await c.patch("/api/status-columns/reorder",
                      json={"items": [{"id": col["id"], "order": i} for i, col in enumerate(cols)]}, headers=h)
        print("✓ status columns reorder persists new order")

        # edit a column key — tasks on it cascade to the new key; dup key rejected
        newcol = (await c.post("/api/status-columns", json={"key": "Review", "name": "Review", "order": 99}, headers=h)).json()
        rtask = (await c.post("/api/tasks", json={"title": "in review", "status": "Review"}, headers=h)).json()
        assert (await c.patch(f"/api/status-columns/{newcol['id']}", json={"key": "CodeReview"}, headers=h)).status_code == 200
        assert (await c.get(f"/api/tasks/{rtask['id']}", headers=h)).json()["status"] == "CodeReview"
        assert (await c.patch(f"/api/status-columns/{newcol['id']}", json={"key": "Done"}, headers=h)).status_code == 409
        print("✓ status column key edit cascades to tasks; duplicate key rejected")

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

        # task comments + one-level replies
        cm = (await c.post(f"/api/tasks/{t1['id']}/comments", json={"body": "first comment"}, headers=h)).json()
        rp = (await c.post(f"/api/tasks/{t1['id']}/comments", json={"body": "a reply", "parent_id": cm["id"]}, headers=h)).json()
        nested = (await c.get(f"/api/tasks/{t1['id']}/comments", headers=h)).json()
        assert len(nested) == 1 and nested[0]["id"] == cm["id"]
        assert len(nested[0]["replies"]) == 1 and nested[0]["replies"][0]["body"] == "a reply"
        # reply-to-reply rejected
        assert (await c.post(f"/api/tasks/{t1['id']}/comments", json={"body": "x", "parent_id": rp["id"]}, headers=h)).status_code == 400
        # viewer cannot comment
        assert (await c.post(f"/api/tasks/{t1['id']}/comments", json={"body": "nope"}, headers=vh)).status_code == 403
        # a member cannot delete someone else's comment; an admin/manager can
        assert (await c.delete(f"/api/tasks/{t1['id']}/comments/{cm['id']}", headers=mh)).status_code == 403
        assert (await c.delete(f"/api/tasks/{t1['id']}/comments/{cm['id']}", headers=h)).status_code == 204
        # deleting the top-level comment removed its reply too
        assert (await c.get(f"/api/tasks/{t1['id']}/comments", headers=h)).json() == []
        print("✓ comments: nested replies, reply-to-reply 400, viewer 403, RBAC delete, cascade")

        # notifications: assign + move + sprint complete; actor never notifies self
        member_me = (await c.get("/api/auth/me", headers=mh)).json()
        bid = member_me["id"]
        nt = (await c.post("/api/tasks", json={"title": "assigned to B", "assignee_id": bid}, headers=h)).json()
        await c.patch(f"/api/tasks/{nt['id']}/move", json={"status": "InProgress", "order": 0}, headers=h)
        nsp = (await c.post("/api/sprints", json={"name": "Notify Sprint", "start_date": "2027-01-04"}, headers=h)).json()
        await c.post(f"/api/sprints/{nsp['id']}/complete", headers=h)
        bn = (await c.get("/api/notifications", headers=mh)).json()
        btypes = set(n["type"] for n in bn["items"])
        assert {"assign", "move", "sprint_complete"} <= btypes, bn
        assert bn["unread"] >= 3, bn
        an = (await c.get("/api/notifications", headers=h)).json()
        assert all(n.get("sprint_id") != nsp["id"] for n in an["items"]), "actor was notified of own action"
        await c.post("/api/notifications/read-all", headers=mh)
        assert (await c.get("/api/notifications", headers=mh)).json()["unread"] == 0
        print("✓ notifications: assign/move/sprint_complete delivered, actor skipped, read-all clears")

        # multi-board: a second board with its own prefix + start number, isolated
        boards = (await c.get("/api/boards", headers=h)).json()
        assert any(b.get("is_default") for b in boards), boards
        nb = (await c.post("/api/boards", json={
            "name": "Beta", "prefix": "BETA", "start_number": 100, "member_ids": [bid],
        }, headers=h)).json()
        nbid = nb["id"]
        # the new board gets its own seeded columns
        bcols = (await c.get(f"/api/status-columns?board_id={nbid}", headers=h)).json()
        assert {col["key"] for col in bcols} == {"TODO", "InProgress", "QA", "Done"}, bcols
        # a task created in the board starts at the configured number with the prefix
        bt = (await c.post("/api/tasks", json={"title": "first beta", "board_id": nbid}, headers=h)).json()
        assert bt["task_number"] == "BETA-100", bt
        assert bt["board_id"] == nbid
        # the board view shows only the board's tasks
        bv = (await c.get(f"/api/tasks/board?board_id={nbid}", headers=h)).json()
        bv_ids = [t["id"] for col in bv["tasks"].values() for t in col]
        assert bt["id"] in bv_ids and t1["id"] not in bv_ids
        # a non-member is denied; a member and admin are allowed
        assert (await c.get(f"/api/tasks/board?board_id={nbid}", headers=vh)).status_code == 403
        assert (await c.get(f"/api/tasks/board?board_id={nbid}", headers=mh)).status_code == 200
        print("✓ multi-board: per-board prefix/start, isolated tasks+columns, membership 403")

        # admin cannot demote/lock out the last admin
        me = (await c.get("/api/auth/me", headers=h)).json()
        lock = await c.patch(f"/api/users/{me['id']}", json={"role": "viewer"}, headers=h)
        assert lock.status_code == 400, lock.status_code
        # malformed id -> 400 (not 500)
        assert (await c.patch("/api/users/not-an-id", json={"role": "member"}, headers=h)).status_code == 400
        print("✓ guards: last-admin lockout blocked (400), malformed id -> 400")

    print("\nALL HTTP INTEGRATION CHECKS PASSED")


asyncio.run(main())
