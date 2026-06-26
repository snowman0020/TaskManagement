from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from app.core.deps import get_current_user, require_member
from app.database import get_db, next_sequence
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.task import TaskCreate, TaskMove, TaskReorder, TaskUpdate

router = APIRouter(prefix="/api/tasks", tags=["tasks"])

TASK_PREFIX = "TASK"


async def _status_context() -> tuple[str, str, set[str]]:
    """Return (first_status_key, done_status_key, {valid_keys})."""
    db = get_db()
    cols = await db.status_columns.find().sort("order", 1).to_list(100)
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


@router.get("")
async def list_tasks(
    status: str | None = None,
    sprint_id: str | None = None,
    assignee_id: str | None = None,
    _=Depends(get_current_user),
):
    query: dict = {}
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
    _=Depends(get_current_user),
):
    """Return columns + tasks grouped by status, ready for the Kanban board.

    `assignee_id` filters to one person's tasks; the sentinel "none" returns
    tasks with no assignee. `sprint_id="none"` returns Backlog (no sprint).
    """
    db = get_db()
    cols = await db.status_columns.find().sort("order", 1).to_list(100)
    query: dict = {}
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
    first_status, done_status, valid = await _status_context()
    status = payload.status or first_status
    _ensure_valid_status(status, valid)

    seq = await next_sequence("task")
    task_number = f"{TASK_PREFIX}-{seq}"

    # place the new task at the TOP of its column: one below the current minimum
    # order in the same column (status + sprint), consistent with the 0..N
    # integer scheme written by the bulk-reorder endpoint.
    col_query = {"status": status, "sprint_id": payload.sprint_id}
    top = await db.tasks.find(col_query).sort("order", 1).limit(1).to_list(1)
    order = (top[0]["order"] - 1) if top else 0

    doc = {
        "task_number": task_number,
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
    await _apply_status_timestamps(doc, status, doc)
    res = await db.tasks.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@router.get("/{task_id}")
async def get_task(task_id: str, _=Depends(get_current_user)):
    doc = await get_db().tasks.find_one({"_id": oid(task_id)})
    if not doc:
        raise HTTPException(status_code=404, detail="Task not found")
    return serialize(doc)


async def _apply_status_timestamps(task: dict, new_status: str, update: dict) -> None:
    """Record started_at / done_at for leadtime metrics on status change."""
    first_status, done_status, _valid = await _status_context()
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

    data = payload.model_dump(exclude_unset=True)
    update = {k: v for k, v in data.items()}
    status_changed = "status" in data and data["status"] != task.get("status")
    if status_changed:
        _, _done, valid = await _status_context()
        _ensure_valid_status(update["status"], valid)
        await _apply_status_timestamps(task, update["status"], update)
    update["updated_at"] = _now()

    res = await db.tasks.find_one_and_update(
        {"_id": oid(task_id)}, {"$set": update}, return_document=True
    )
    if status_changed:
        await _log_move(task, task.get("status"), data["status"], current)
    return serialize(res)


@router.patch("/{task_id}/move")
async def move_task(task_id: str, payload: TaskMove, current=Depends(require_member)):
    """Drag-and-drop: change a task's status column and ordering position."""
    db = get_db()
    task = await db.tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    _, _done, valid = await _status_context()
    _ensure_valid_status(payload.status, valid)

    update: dict = {"status": payload.status, "order": payload.order, "updated_at": _now()}
    if payload.status != task.get("status"):
        await _apply_status_timestamps(task, payload.status, update)

    res = await db.tasks.find_one_and_update(
        {"_id": oid(task_id)}, {"$set": update}, return_document=True
    )
    if payload.status != task.get("status"):
        await _log_move(task, task.get("status"), payload.status, current)
    return serialize(res)


@router.patch("/reorder/bulk")
async def reorder_tasks(payload: TaskReorder, current=Depends(require_member)):
    """Persist a batch of order/status changes after a drag-and-drop drop."""
    db = get_db()
    _, _done, valid = await _status_context()
    for item in payload.items:
        _ensure_valid_status(item.status, valid)
    for item in payload.items:
        task = await db.tasks.find_one({"_id": oid(item.id)})
        if not task:
            continue
        update: dict = {
            "status": item.status,
            "order": item.order,
            "updated_at": _now(),
        }
        moved = item.status != task.get("status")
        if moved:
            await _apply_status_timestamps(task, item.status, update)
        await db.tasks.update_one({"_id": oid(item.id)}, {"$set": update})
        if moved:
            await _log_move(task, task.get("status"), item.status, current)
    return {"updated": len(payload.items)}


@router.get("/{task_id}/history")
async def task_history(task_id: str, _=Depends(get_current_user)):
    """Return a task's move history (status changes), newest first."""
    docs = await get_db().activity_log.find({"task_id": task_id}).sort("at", -1).to_list(500)
    return serialize_list(docs)


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: str, _=Depends(require_member)):
    res = await get_db().tasks.delete_one({"_id": oid(task_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Task not found")
