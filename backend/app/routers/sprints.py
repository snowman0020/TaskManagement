import re
from datetime import date, datetime, time, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_manager
from app.database import get_db
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.sprint import SprintCreate, SprintGenerate, SprintUpdate
from app.services.sprint_service import build_sprints, sprint_end_date, working_days

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


def _to_dt(d, end_of_day=False):
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t, tzinfo=timezone.utc)


def _snap_to_monday(d: date) -> date:
    """Sprints start on a Monday; snap a non-Monday start forward."""
    return d + timedelta(days=(7 - d.weekday()) % 7) if d.weekday() != 0 else d


@router.get("")
async def list_sprints(_=Depends(get_current_user)):
    docs = await get_db().sprints.find().sort("start_date", 1).to_list(500)
    return serialize_list(docs)


@router.post("", status_code=201)
async def create_sprint(payload: SprintCreate, _=Depends(require_manager)):
    db = get_db()
    if await db.sprints.find_one({"name": payload.name}):
        raise HTTPException(status_code=409, detail="Sprint name already exists")
    # sprint_end_date assumes a Monday start; snap so end lands on a Friday
    start = _snap_to_monday(payload.start_date)
    end = sprint_end_date(start, payload.weeks)
    doc = {
        "name": payload.name,
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
async def generate_sprints(payload: SprintGenerate, _=Depends(require_manager)):
    """Auto-create consecutive 2-week (Mon-Fri) sprints."""
    db = get_db()
    sprints = build_sprints(
        payload.start_date,
        payload.count,
        payload.weeks,
        payload.name_prefix,
        payload.manday,
    )
    # continue numbering past any existing "<prefix> N" sprints so repeated
    # calls extend the schedule instead of silently colliding on the unique name.
    base = await db.sprints.count_documents(
        {"name": {"$regex": rf"^{re.escape(payload.name_prefix)} \d+$"}}
    )
    created, skipped = [], []
    for offset, s in enumerate(sprints, start=base):
        s["name"] = f"{payload.name_prefix} {offset + 1}"
        if await db.sprints.find_one({"name": s["name"]}):
            skipped.append(s["name"])
            continue
        res = await db.sprints.insert_one(s)
        s["_id"] = res.inserted_id
        created.append(serialize(s))
    return {"created": len(created), "skipped": skipped, "sprints": created}


@router.patch("/{sprint_id}")
async def update_sprint(sprint_id: str, payload: SprintUpdate, _=Depends(require_manager)):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await get_db().sprints.find_one_and_update(
        {"_id": oid(sprint_id)}, {"$set": data}, return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return serialize(res)


@router.post("/{sprint_id}/complete")
async def complete_sprint(sprint_id: str, _=Depends(require_manager)):
    """Mark a sprint completed and permanently delete its done tasks.

    Only tasks in THIS sprint whose status is a done column are removed;
    backlog and other sprints are left untouched.
    """
    db = get_db()
    sprint = await db.sprints.find_one({"_id": oid(sprint_id)})
    if not sprint:
        raise HTTPException(status_code=404, detail="Sprint not found")

    cols = await db.status_columns.find().sort("order", 1).to_list(100)
    done_keys = [c["key"] for c in cols if c.get("is_done")]
    if not done_keys and cols:
        done_keys = [cols[-1]["key"]]  # fallback: treat the last column as done

    res = await db.tasks.delete_many(
        {"sprint_id": sprint_id, "status": {"$in": done_keys}}
    )
    await db.sprints.update_one(
        {"_id": oid(sprint_id)}, {"$set": {"status": "completed"}}
    )
    sprint = await db.sprints.find_one({"_id": oid(sprint_id)})
    return {"deleted": res.deleted_count, "sprint": serialize(sprint)}


@router.delete("/{sprint_id}", status_code=204)
async def delete_sprint(sprint_id: str, _=Depends(require_manager)):
    res = await get_db().sprints.delete_one({"_id": oid(sprint_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Sprint not found")
