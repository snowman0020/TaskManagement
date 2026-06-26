from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from app.config import settings


class Mongo:
    client: AsyncIOMotorClient | None = None
    db: AsyncIOMotorDatabase | None = None


mongo = Mongo()


async def connect_to_mongo() -> None:
    mongo.client = AsyncIOMotorClient(settings.mongo_uri)
    mongo.db = mongo.client[settings.mongo_db]
    await _ensure_indexes()


async def close_mongo_connection() -> None:
    if mongo.client:
        mongo.client.close()


def get_db() -> AsyncIOMotorDatabase:
    assert mongo.db is not None, "Database not initialised"
    return mongo.db


async def _ensure_indexes() -> None:
    db = get_db()
    # Drop obsolete global-unique indexes — column keys and sprint names are now
    # unique per board, not globally (left over from the pre-multi-board schema).
    for coll, idx in ((db.status_columns, "key_1"), (db.sprints, "name_1")):
        try:
            await coll.drop_index(idx)
        except Exception:
            pass

    await db.users.create_index("username", unique=True)
    await db.users.create_index("email", unique=True)
    await db.tasks.create_index("task_number", unique=True)
    await db.tasks.create_index("status")
    await db.tasks.create_index("sprint_id")
    await db.tasks.create_index("board_id")
    await db.tasks.create_index([("status", 1), ("order", 1)])
    await db.sprints.create_index("board_id")
    await db.status_columns.create_index("board_id")
    await db.status_columns.create_index("order")
    await db.boards.create_index("member_ids")
    await db.activity_log.create_index([("task_id", 1), ("at", -1)])
    await db.comments.create_index([("task_id", 1), ("created_at", 1)])
    await db.notifications.create_index([("user_id", 1), ("created_at", -1)])
    await db.notifications.create_index([("user_id", 1), ("read", 1)])


async def next_sequence(name: str) -> int:
    """Atomically increment and return a running counter (for task numbers)."""
    db = get_db()
    doc = await db.counters.find_one_and_update(
        {"_id": name},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=True,
    )
    return doc["seq"]
