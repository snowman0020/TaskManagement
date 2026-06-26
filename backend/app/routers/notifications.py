from fastapi import APIRouter, Depends

from app.core.deps import get_current_user
from app.database import get_db
from app.schemas.common import serialize_list

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("")
async def list_notifications(current=Depends(get_current_user)):
    db = get_db()
    uid = str(current["_id"])
    docs = await db.notifications.find({"user_id": uid}).sort("created_at", -1).to_list(50)
    unread = await db.notifications.count_documents({"user_id": uid, "read": False})
    return {"items": serialize_list(docs), "unread": unread}


@router.post("/read-all")
async def mark_all_read(current=Depends(get_current_user)):
    db = get_db()
    res = await db.notifications.update_many(
        {"user_id": str(current["_id"]), "read": False}, {"$set": {"read": True}}
    )
    return {"updated": res.modified_count}


@router.delete("")
async def clear_all(current=Depends(get_current_user)):
    """Delete all of the current user's notifications."""
    res = await get_db().notifications.delete_many({"user_id": str(current["_id"])})
    return {"deleted": res.deleted_count}
