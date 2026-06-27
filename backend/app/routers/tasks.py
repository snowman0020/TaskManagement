from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user, require_member
from app.database import get_db, next_sequence
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.task import TaskCreate, TaskMove, TaskReorder, TaskUpdate
from app.services.access import ensure_board_access, resolve_board_id
from app.services.cleanup import purge_task_refs
from app.services.notifications import notify

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _status_context(board_id: str) -> tuple[str, str, set[str]]:
    """Return (first_status_key, done_status_key, {valid_keys}) for a board."""
    db = get_db()
    cols = await db.status_columns.find({"board_id": board_id}).sort("order", 1).to_list(100)
    if not cols:
        return "TODO", "Done", {"TODO", "InProgress", "QA", "Done"}
    first = cols[0]["key"]
    done = next((c["key"] for c in cols if c.get("is_done")), cols[-1]["key"])
    return first, done, {c["key"] for c in cols}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _ensure_valid_status(status: str, valid: set[str]) -> None:
    if status not in valid:
        raise HTTPException(status_code=400, detail=f"Unknown status: {status}")


async def _ensure_sprint_on_board(sprint_id: str | None, board_id: str) -> None:
    """A task may only reference a sprint that lives on the same board."""
    if not sprint_id:
        return
    sp = await get_db().sprints.find_one({"_id": oid(sprint_id)})
    if not sp or sp.get("board_id") != board_id:
        raise HTTPException(status_code=400, detail="Sprint not found on this board")


async def _log_move(task: dict, from_status: str, to_status: str, user: dict) -> None:
    """Record a task status change in the activity log (best-effort)."""
    if from_status == to_status:
        return
    try:
        await get_db().activity_log.insert_one(
            {
                "task_id": str(task["_id"]),
                "task_number": task.get("task_number"),
                "action": "move",
                "user_id": str(user["_id"]),
                "username": user.get("username"),
                "from_status": from_status,
                "to_status": to_status,
                "at": _now(),
            }
        )
    except Exception:
        # auditing must never fail the move itself
        pass


async def _status_name(key: str, board_id: str) -> str:
    col = await get_db().status_columns.find_one({"key": key, "board_id": board_id})
    return col["name"] if col else key


async def _notify_move(task: dict, new_status: str, assignee: str | None, actor: dict) -> None:
    """Tell a task's assignee and its creator it was moved.

    notify() drops empty ids, deduplicates, and skips the actor, so the person
    doing the move is never notified even if they are the assignee or reporter.
    """
    recipients = [assignee, task.get("reporter_id")]
    if not any(recipients):
        return
    name = await _status_name(new_status, task.get("board_id"))
    await notify(
        recipients,
        "move",
        f"{task.get('task_number')} moved to {name} by {actor.get('username')}",
        actor_id=str(actor["_id"]),
        task_id=str(task["_id"]),
    )


async def _notify_assign(task: dict, assignee: str, actor: dict) -> None:
    await notify(
        [assignee],
        "assign",
        f"{actor.get('username')} assigned {task.get('task_number')} to you",
        actor_id=str(actor["_id"]),
        task_id=str(task["_id"]),
    )


@router.get("")
async def list_tasks(
    status: str | None = None,
    sprint_id: str | None = None,
    assignee_id: str | None = None,
    board_id: str | None = None,
    current=Depends(get_current_user),
):
    board_id = await resolve_board_id(board_id)
    await ensure_board_access(board_id, current)
    query: dict = {"board_id": board_id}
    if status:
        query["status"] = status
    if sprint_id:
        query["sprint_id"] = sprint_id
    if assignee_id:
        query["assignee_id"] = assignee_id
    docs = await get_db().tasks.find(query).sort([("status", 1), ("order", 1)]).to_list(
        5000
    )
    return serialize_list(docs)


@router.get("/board")
async def board(
    sprint_id: str | None = Query(default=None),
    assignee_id: str | None = Query(default=None),
    board_id: str | None = Query(default=None),
    current=Depends(get_current_user),
):
    """Return columns + tasks grouped by status, ready for the Kanban board.

    `assignee_id` filters to one person's tasks; the sentinel "none" returns
    tasks with no assignee. `sprint_id="none"` returns Backlog (no sprint).
    Everything is scoped to `board_id` (the Default board when omitted).
    """
    db = get_db()
    board_id = await resolve_board_id(board_id)
    await ensure_board_access(board_id, current)
    cols = await db.status_columns.find({"board_id": board_id}).sort("order", 1).to_list(100)
    query: dict = {"board_id": board_id}
    if sprint_id == "none":
        query["sprint_id"] = None  # Backlog — matches null or missing
    elif sprint_id:
        query["sprint_id"] = sprint_id
    if assignee_id == "none":
        query["assignee_id"] = None  # matches null or missing
    elif assignee_id:
        query["assignee_id"] = assignee_id
    tasks = await db.tasks.find(query).sort("order", 1).to_list(5000)

    grouped: dict[str, list] = {c["key"]: [] for c in cols}
    for t in serialize_list(tasks):
        grouped.setdefault(t["status"], []).append(t)
    return {
        "columns": serialize_list(cols),
        "tasks": grouped,
    }


@router.post("", status_code=201)
async def create_task(payload: TaskCreate, current=Depends(require_member)):
    db = get_db()
    board_id = await resolve_board_id(payload.board_id)
    board = await ensure_board_access(board_id, current)

    first_status, done_status, valid = await _status_context(board_id)
    status = payload.status or first_status
    _ensure_valid_status(status, valid)
    await _ensure_sprint_on_board(payload.sprint_id, board_id)

    # running number is per board: <board prefix>-<board counter>
    prefix = board.get("prefix", "TASK")
    seq = await next_sequence(f"task:{board_id}")
    task_number = f"{prefix}-{seq}"

    # place the new task at the TOP of its column: one below the current minimum
    # order in the same column (board + status + sprint), consistent with the
    # 0..N integer scheme written by the bulk-reorder endpoint.
    col_query = {"board_id": board_id, "status": status, "sprint_id": payload.sprint_id}
    top = await db.tasks.find(col_query).sort("order", 1).limit(1).to_list(1)
    order = (top[0]["order"] - 1) if top else 0

    doc = {
        "task_number": task_number,
        "board_id": board_id,
        "title": payload.title,
        "description": payload.description,
        "status": status,
        "priority": payload.priority,
        "assignee_id": payload.assignee_id,
        "reporter_id": str(current["_id"]),
        "sprint_id": payload.sprint_id,
        "story_points": payload.story_points,
        "due_date": payload.due_date,
        "images": [],
        "order": order,
        "created_at": _now(),
        "updated_at": _now(),
        "started_at": None,
        "done_at": None,
    }
    # stamp started_at/done_at when a task is created directly in a non-first /
    # done column so leadtime & cycle-time metrics stay accurate.
    await _apply_status_timestamps(doc, status, doc, board_id)
    res = await db.tasks.insert_one(doc)
    doc["_id"] = res.inserted_id
    # notify the assignee if the task is created already assigned to someone else
    if payload.assignee_id:
        await _notify_assign(doc, payload.assignee_id, current)
    return serialize(doc)


@router.get("/{task_id}")
async def get_task(task_id: str, current=Depends(get_current_user)):
    doc = await get_db().tasks.find_one({"_id": oid(task_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    await ensure_board_access(doc.get("board_id"), current)
    return serialize(doc)


async def _apply_status_timestamps(task: dict, new_status: str, update: dict, board_id: str) -> None:
    """Record started_at / done_at for leadtime metrics on status change."""
    first_status, done_status, _valid = await _status_context(board_id)
    # only stamp started_at for genuine in-progress columns (not a straight
    # first -> done jump, which would make cycle time meaninglessly ~0)
    if (
        new_status != first_status
        and new_status != done_status
        and not task.get("started_at")
    ):
        update["started_at"] = _now()
    if new_status == done_status and not task.get("done_at"):
        update["done_at"] = _now()
    if new_status != done_status:
        update["done_at"] = None  # reopened


@router.patch("/{task_id}")
async def update_task(task_id: str, payload: TaskUpdate, current=Depends(require_member)):
    db = get_db()
    task = await db.tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    board_id = task.get("board_id")
    await ensure_board_access(board_id, current)
    data = payload.model_dump(exclude_unset=True)
    if "sprint_id" in data:
        await _ensure_sprint_on_board(data["sprint_id"], board_id)
    update = {k: v for k, v in data.items()}
    status_changed = "status" in data and data["status"] != task.get("status")
    new_assignee = data["assignee_id"] if "assignee_id" in data else task.get("assignee_id")
    assignee_changed = (
        "assignee_id" in data
        and data["assignee_id"]
        and data["assignee_id"] != task.get("assignee_id")
    )
    if status_changed:
        _, _done, valid = await _status_context(board_id)
        _ensure_valid_status(update["status"], valid)
        await _apply_status_timestamps(task, update["status"], update, board_id)
    update["updated_at"] = _now()

    res = await db.tasks.find_one_and_update(
        {"_id": oid(task_id)}, {"$set": update}, return_document=True
    )
    if status_changed:
        await _log_move(task, task.get("status"), data["status"], current)
        # if the assignee also changed, the assign-notify below is the right one
        if not assignee_changed:
            await _notify_move(task, data["status"], new_assignee, current)
    if assignee_changed:
        await _notify_assign(task, data["assignee_id"], current)
    return serialize(res)


@router.patch("/{task_id}/move")
async def move_task(task_id: str, payload: TaskMove, current=Depends(require_member)):
    """Drag-and-drop: change a task's status column and ordering position."""
    db = get_db()
    task = await db.tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    board_id = task.get("board_id")
    await ensure_board_access(board_id, current)
    _, _done, valid = await _status_context(board_id)
    _ensure_valid_status(payload.status, valid)

    update: dict = {"status": payload.status, "order": payload.order, "updated_at": _now()}
    if payload.status != task.get("status"):
        await _apply_status_timestamps(task, payload.status, update, board_id)

    res = await db.tasks.find_one_and_update(
        {"_id": oid(task_id)}, {"$set": update}, return_document=True
    )
    if payload.status != task.get("status"):
        await _log_move(task, task.get("status"), payload.status, current)
        await _notify_move(task, payload.status, task.get("assignee_id"), current)
    return serialize(res)


@router.patch("/reorder/bulk")
async def reorder_tasks(payload: TaskReorder, current=Depends(require_member)):
    """Persist a batch of order/status changes after a drag-and-drop drop."""
    db = get_db()
    for item in payload.items:
        task = await db.tasks.find_one({"_id": oid(item.id)})
        if not task:
            continue
        board_id = task.get("board_id")
        await ensure_board_access(board_id, current)
        _, _done, valid = await _status_context(board_id)
        _ensure_valid_status(item.status, valid)
        update: dict = {
            "status": item.status,
            "order": item.order,
            "updated_at": _now(),
        }
        moved = item.status != task.get("status")
        if moved:
            await _apply_status_timestamps(task, item.status, update, board_id)
        await db.tasks.update_one({"_id": oid(item.id)}, {"$set": update})
        if moved:
            await _log_move(task, task.get("status"), item.status, current)
            await _notify_move(task, item.status, task.get("assignee_id"), current)
    return {"updated": len(payload.items)}


@router.get("/{task_id}/history")
async def task_history(task_id: str, current=Depends(get_current_user)):
    """Return a task's move history (status changes), newest first."""
    db = get_db()
    task = await db.tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await ensure_board_access(task.get("board_id"), current)
    docs = await db.activity_log.find({"task_id": task_id}).sort("at", -1).to_list(500)
    return serialize_list(docs)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, current=Depends(require_member)):
    db = get_db()
    task = await db.tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    await ensure_board_access(task.get("board_id"), current)
    await purge_task_refs([task])  # drop its images/comments/history/notifications
    await db.tasks.delete_one({"_id": oid(task_id)})
