from datetime import datetime, timezone

from app.database import get_db


async def notify(
    user_ids,
    type_: str,
    message: str,
    actor_id: str | None = None,
    task_id: str | None = None,
    sprint_id: str | None = None,
) -> None:
    """Insert a notification per recipient, skipping the actor and duplicates.

    Best-effort: a failure here must never break the action that triggered it.
    """
    now = datetime.now(timezone.utc)
    docs = []
    seen: set[str] = set()
    for uid in user_ids:
        if not uid or uid == actor_id or uid in seen:
            continue
        seen.add(uid)
        docs.append(
            {
                "user_id": uid,
                "type": type_,
                "message": message,
                "task_id": task_id,
                "sprint_id": sprint_id,
                "read": False,
                "created_at": now,
            }
        )
    if not docs:
        return
    try:
        await get_db().notifications.insert_many(docs)
    except Exception:
        pass
