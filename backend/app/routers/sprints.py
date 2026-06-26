import re
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_manager
from app.database import get_db
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.sprint import SprintCreate, SprintGenerate, SprintUpdate
from app.services.access import ensure_board_access, resolve_board_id
from app.services.cleanup import purge_task_refs
from app.services.notifications import notify
from app.services.sprint_service import build_sprints, sprint_end_date, working_days

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


def _to_dt(d, end_of_day=False):
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t, tzinfo=timezone.utc)


def _snap_to_monday(d: date) -> date:
    """Sprints start on a Monday; snap a non-Monday start forward."""
    return d + timedelta(days=(7 - d.weekday()) % 7) if d.weekday() != 0 else d


@router.get("")
async def list_sprints(board_id: str | None = None, current=Depends(get_current_user)):
    board_id = await resolve_board_id(board_id)
    await ensure_board_access(board_id, current)
    docs = await get_db().sprints.find({"board_id": board_id}).sort("start_date", 1).to_list(500)
    return serialize_list(docs)


@router.post("", status_code=201)
async def create_sprint(payload: SprintCreate, current=Depends(require_manager)):
    db = get_db()
    board_id = await resolve_board_id(payload.board_id)
    await ensure_board_access(board_id, current)
    if await db.sprints.find_one({"name": payload.name, "board_id": board_id}):
        raise HTTPException(status_code=409, detail="Sprint name already exists")
    # sprint_end_date assumes a Monday start; snap so end lands on a Friday
    start = _snap_to_monday(payload.start_date)
    end = sprint_end_date(start, payload.weeks)
    doc = {
        "name": payload.name,
        "board_id": board_id,
        "start_date": _to_dt(start),
        "end_date": _to_dt(end, end_of_day=True),
        "working_days": working_days(start, end),
        "weeks": payload.weeks,
        "goal": payload.goal,
        "status": "planned",
        "manday": payload.manday,
    }
    res = await db.sprints.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@router.post("/generate", status_code=201)
async def generate_sprints(payload: SprintGenerate, current=Depends(require_manager)):
    """Auto-create consecutive 2-week (Mon-Fri) sprints."""
    db = get_db()
    board_id = await resolve_board_id(payload.board_id)
    await ensure_board_access(board_id, current)
    sprints = build_sprints(
        payload.start_date,
        payload.count,
        payload.weeks,
        payload.name_prefix,
        payload.manday,
    )
    # continue numbering past existing "<prefix> N" sprints ON THIS BOARD so
    # repeated calls extend the schedule instead of colliding on the name.
    base = await db.sprints.count_documents(
        {"board_id": board_id, "name": {"$regex": rf"^{re.escape(payload.name_prefix)} \d+$"}}
    )
    created, skipped = [], []
    for offset, s in enumerate(sprints, start=base):
        s["name"] = f"{payload.name_prefix} {offset + 1}"
        s["board_id"] = board_id
        if await db.sprints.find_one({"name": s["name"], "board_id": board_id}):
            skipped.append(s["name"])
            continue
        res = await db.sprints.insert_one(s)
        s["_id"] = res.inserted_id
        created.append(serialize(s))
    return {"created": len(created), "skipped": skipped, "sprints": created}


@router.patch("/{sprint_id}")
async def update_sprint(sprint_id: str, payload: SprintUpdate, current=Depends(require_manager)):
    db = get_db()
    sprint = await db.sprints.find_one({"_id": oid(sprint_id)})
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await ensure_board_access(sprint.get("board_id"), current)
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await db.sprints.find_one_and_update(
        {"_id": oid(sprint_id)}, {"$set": data}, return_document=True
    )
    return serialize(res)


@router.post("/{sprint_id}/complete")
async def complete_sprint(sprint_id: str, current=Depends(require_manager)):
    """Mark a sprint completed and permanently delete its done tasks.

    Only tasks in THIS sprint whose status is a done column are removed;
    backlog and other sprints are left untouched.
    """
    db = get_db()
    sprint = await db.sprints.find_one({"_id": oid(sprint_id)})
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    board_id = sprint.get("board_id")
    await ensure_board_access(board_id, current)

    cols = await db.status_columns.find(
        {"board_id": board_id}
    ).sort("order", 1).to_list(100)
    done_keys = [c["key"] for c in cols if c.get("is_done")]
    if not done_keys and cols:
        done_keys = [cols[-1]["key"]]  # fallback: treat the last column as done

    # delete this board+sprint's done tasks (scoped by board_id so a foreign
    # task that wrongly carries this sprint_id can never be swept up) + their refs
    done_filter = {"board_id": board_id, "sprint_id": sprint_id, "status": {"$in": done_keys}}
    done_tasks = await db.tasks.find(done_filter).to_list(5000)
    await purge_task_refs(done_tasks)
    res = await db.tasks.delete_many(done_filter)
    await db.sprints.update_one(
        {"_id": oid(sprint_id)}, {"$set": {"status": "completed"}}
    )
    sprint = await db.sprints.find_one({"_id": oid(sprint_id)})

    # notify the board's members (the default board is open, so notify everyone)
    board = await db.boards.find_one({"_id": oid(board_id)}) if board_id else None
    if board and not board.get("is_default"):
        recipients = board.get("member_ids") or []  # empty list -> notify nobody
    else:
        users = await db.users.find({"is_active": True}).to_list(1000)
        recipients = [str(u["_id"]) for u in users]
    await notify(
        recipients,
        "sprint_complete",
        f"{current.get('username')} completed sprint {sprint['name']}",
        actor_id=str(current["_id"]),
        sprint_id=sprint_id,
    )
    return {"deleted": res.deleted_count, "sprint": serialize(sprint)}


@router.delete("/{sprint_id}", status_code=204)
async def delete_sprint(sprint_id: str, current=Depends(require_manager)):
    db = get_db()
    sprint = await db.sprints.find_one({"_id": oid(sprint_id)})
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")
    await ensure_board_access(sprint.get("board_id"), current)
    await db.sprints.delete_one({"_id": oid(sprint_id)})
    await db.notifications.delete_many({"sprint_id": sprint_id})
