from datetime import datetime, timezone

from app.config import settings
from app.core.security import hash_password
from app.database import get_db
from app.models.user import Role


def _now() -> datetime:
    return datetime.now(timezone.utc)


DEFAULT_COLUMNS = [
    {"key": "TODO", "name": "To Do", "order": 0, "wip_limit": None, "is_done": False},
    {"key": "InProgress", "name": "In Progress", "order": 1, "wip_limit": 5, "is_done": False},
    {"key": "QA", "name": "QA", "order": 2, "wip_limit": 3, "is_done": False},
    {"key": "Done", "name": "Done", "order": 3, "wip_limit": None, "is_done": True},
]


async def seed_defaults() -> None:
    db = get_db()

    # Seed default status columns (configurable later via admin page)
    if await db.status_columns.count_documents({}) == 0:
        await db.status_columns.insert_many([dict(c) for c in DEFAULT_COLUMNS])

    # Seed the first admin account
    if await db.users.count_documents({}) == 0:
        await db.users.insert_one(
            {
                "username": settings.admin_username,
                "email": settings.admin_email,
                "full_name": "Administrator",
                "role": Role.ADMIN.value,
                "hashed_password": hash_password(settings.admin_password),
                "is_active": True,
            }
        )

    # Multi-board: ensure a Default board and backfill existing data into it.
    default = await db.boards.find_one({"is_default": True})
    if not default:
        users = await db.users.find().to_list(1000)
        res = await db.boards.insert_one(
            {
                "name": "Default",
                "prefix": "TASK",
                "member_ids": [str(u["_id"]) for u in users],
                "is_default": True,
                "created_at": _now(),
            }
        )
        default_id = str(res.inserted_id)
    else:
        default_id = str(default["_id"])

    # backfill board_id on any legacy task / sprint / column
    for coll in (db.tasks, db.sprints, db.status_columns):
        await coll.update_many(
            {"board_id": {"$exists": False}}, {"$set": {"board_id": default_id}}
        )

    # move the legacy global task counter into the default board
    legacy = await db.counters.find_one({"_id": "task"})
    if legacy and not await db.counters.find_one({"_id": f"task:{default_id}"}):
        await db.counters.update_one(
            {"_id": f"task:{default_id}"},
            {"$set": {"seq": legacy.get("seq", 0)}},
            upsert=True,
        )
