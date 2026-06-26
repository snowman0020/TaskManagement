from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.deps import get_current_user, require_member
from app.database import get_db
from app.models.user import Role
from app.schemas.comment import CommentCreate
from app.schemas.common import oid, serialize, serialize_list
from app.services.access import ensure_board_access

router = APIRouter(prefix="/api/tasks/{task_id}/comments", tags=["comments"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _task_or_404(task_id: str) -> dict:
    task = await get_db().tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.get("")
async def list_comments(task_id: str, current=Depends(get_current_user)):
    """Return the task's comments nested as top-level + their replies."""
    db = get_db()
    task = await _task_or_404(task_id)
    await ensure_board_access(task.get("board_id"), current)
    docs = serialize_list(
        await db.comments.find({"task_id": task_id}).sort("created_at", 1).to_list(2000)
    )
    replies: dict[str, list] = {}
    for d in docs:
        if d.get("parent_id"):
            replies.setdefault(d["parent_id"], []).append(d)
    tops = [d for d in docs if not d.get("parent_id")]
    for t in tops:
        t["replies"] = replies.get(t["id"], [])
    return tops


@router.post("", status_code=201)
async def add_comment(task_id: str, payload: CommentCreate, current=Depends(require_member)):
    db = get_db()
    task = await _task_or_404(task_id)
    await ensure_board_access(task.get("board_id"), current)

    if payload.parent_id:
        parent = await db.comments.find_one({"_id": oid(payload.parent_id)})
        if not parent or parent.get("task_id") != task_id:
            raise HTTPException(status_code=400, detail="Parent comment not found on this task")
        if parent.get("parent_id"):
            raise HTTPException(status_code=400, detail="Cannot reply to a reply")

    doc = {
        "task_id": task_id,
        "user_id": str(current["_id"]),
        "username": current.get("username"),
        "body": payload.body,
        "parent_id": payload.parent_id,
        "created_at": _now(),
    }
    res = await db.comments.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@router.delete("/{comment_id}", status_code=204)
async def delete_comment(task_id: str, comment_id: str, current=Depends(require_member)):
    db = get_db()
    task = await _task_or_404(task_id)
    await ensure_board_access(task.get("board_id"), current)
    comment = await db.comments.find_one({"_id": oid(comment_id)})
    if not comment or comment.get("task_id") != task_id:
        raise HTTPException(status_code=404, detail="Comment not found")

    is_owner = comment.get("user_id") == str(current["_id"])
    is_manager = current.get("role") in (Role.ADMIN, Role.MANAGER)
    if not (is_owner or is_manager):
        raise HTTPException(status_code=403, detail="Not allowed to delete this comment")

    await db.comments.delete_one({"_id": oid(comment_id)})
    # a top-level comment takes its replies with it
    if not comment.get("parent_id"):
        await db.comments.delete_many({"parent_id": comment_id})
    return Response(status_code=204)
