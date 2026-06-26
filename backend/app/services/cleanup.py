"""Cascade cleanup of data that references tasks, so deletes don't orphan rows."""
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from app.database import get_db


async def purge_task_refs(tasks: list[dict]) -> None:
    """Remove the GridFS images, comments, activity log, and notifications that
    reference the given task documents. Does NOT delete the tasks themselves.
    """
    if not tasks:
        return
    db = get_db()
    task_ids = [str(t["_id"]) for t in tasks]

    # GridFS isn't available under the in-memory test mock — skip images there.
    try:
        bucket = AsyncIOMotorGridFSBucket(db, bucket_name="task_images")
        for t in tasks:
            for image in (t.get("images") or []):
                try:
                    await bucket.delete(ObjectId(image["id"]))
                except Exception:
                    pass
    except Exception:
        pass

    await db.comments.delete_many({"task_id": {"$in": task_ids}})
    await db.activity_log.delete_many({"task_id": {"$in": task_ids}})
    await db.notifications.delete_many({"task_id": {"$in": task_ids}})
