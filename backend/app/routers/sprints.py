from datetime import datetime, time, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_manager
from app.database import get_db
from app.schemas.common import serialize, serialize_list
from app.schemas.sprint import SprintCreate, SprintGenerate, SprintUpdate
from app.services.sprint_service import build_sprints, sprint_end_date, working_days

router = APIRouter(prefix="/api/sprints", tags=["sprints"])


def _to_dt(d, end_of_day=False):
    t = time(23, 59, 59) if end_of_day else time(0, 0, 0)
    return datetime.combine(d, t, tzinfo=timezone.utc)


@router.get("")
async def list_sprints(_=Depends(get_current_user)):
    docs = await get_db().sprints.find().sort("start_date", 1).to_list(500)
    return serialize_list(docs)


@router.post("", status_code=201)
async def create_sprint(payload: SprintCreate, _=Depends(require_manager)):
    db = get_db()
    if await db.sprints.find_one({"name": payload.name}):
        raise HTTPException(status_code=409, detail="Sprint name already exists")
    end = sprint_end_date(payload.start_date, payload.weeks)
    doc = {
        "name": payload.name,
        "start_date": _to_dt(payload.start_date),
        "end_date": _to_dt(end, end_of_day=True),
        "working_days": working_days(payload.start_date, end),
        "weeks": payload.weeks,
        "goal": payload.goal,
        "status": "planned",
    }
    res = await db.sprints.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@router.post("/generate", status_code=201)
async def generate_sprints(payload: SprintGenerate, _=Depends(require_manager)):
    """Auto-create consecutive 2-week (Mon-Fri) sprints."""
    db = get_db()
    sprints = build_sprints(
        payload.start_date, payload.count, payload.weeks, payload.name_prefix
    )
    created = []
    for s in sprints:
        if await db.sprints.find_one({"name": s["name"]}):
            continue
        res = await db.sprints.insert_one(s)
        s["_id"] = res.inserted_id
        created.append(serialize(s))
    return {"created": len(created), "sprints": created}


@router.patch("/{sprint_id}")
async def update_sprint(sprint_id: str, payload: SprintUpdate, _=Depends(require_manager)):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await get_db().sprints.find_one_and_update(
        {"_id": ObjectId(sprint_id)}, {"$set": data}, return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Sprint not found")
    return serialize(res)


@router.delete("/{sprint_id}", status_code=204)
async def delete_sprint(sprint_id: str, _=Depends(require_manager)):
    res = await get_db().sprints.delete_one({"_id": ObjectId(sprint_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Sprint not found")
