"""In-process end-to-end smoke test using mongomock (no real MongoDB needed)."""
import asyncio
import os
import sys
from datetime import date

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from mongomock_motor import AsyncMongoMockClient

import app.database as database
from app.database import next_sequence
from app.services.seed import seed_defaults
from app.services.sprint_service import build_sprints


async def main():
    # Wire a mock Mongo client into the app
    client = AsyncMongoMockClient()
    database.mongo.client = client
    database.mongo.db = client["taskmanagement_test"]

    await seed_defaults()
    db = database.get_db()

    # 1. seed created admin + 4 columns
    assert await db.users.count_documents({}) == 1
    assert await db.status_columns.count_documents({}) == 4
    cols = await db.status_columns.find().sort("order", 1).to_list(10)
    assert [c["key"] for c in cols] == ["TODO", "InProgress", "QA", "Done"]
    print("✓ seed: admin + columns TODO/InProgress/QA/Done")

    # 2. running task numbers are sequential
    n1, n2, n3 = await next_sequence("task"), await next_sequence("task"), await next_sequence("task")
    assert (n1, n2, n3) == (1, 2, 3), (n1, n2, n3)
    print(f"✓ running number: TASK-{n1}, TASK-{n2}, TASK-{n3}")

    # 3. sprint generation: 2-week Mon-Fri
    sprints = build_sprints(date(2026, 6, 29), 2, 2, "Sprint")
    for s in sprints:
        await db.sprints.insert_one(s)
    s0 = sprints[0]
    assert s0["start_date"].strftime("%a") == "Mon"
    assert s0["end_date"].strftime("%a") == "Fri"
    assert s0["working_days"] == 10
    print(f"✓ sprint: {s0['name']} {s0['start_date'].date()}→{s0['end_date'].date()} "
          f"({s0['working_days']} working days)")

    print("\nALL SMOKE CHECKS PASSED")


asyncio.run(main())
