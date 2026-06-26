from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_manager
from app.database import get_db
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.sprint import StatusColumnCreate, StatusColumnUpdate

router = APIRouter(prefix="/api/status-columns", tags=["status-columns"])


@router.get("")
async def list_columns(_=Depends(get_current_user)):
    docs = await get_db().status_columns.find().sort("order", 1).to_list(100)
    return serialize_list(docs)


@router.post("", status_code=201)
async def create_column(payload: StatusColumnCreate, _=Depends(require_manager)):
    db = get_db()
    if await db.status_columns.find_one({"key": payload.key}):
        raise HTTPException(status_code=409, detail="Column key already exists")
    doc = payload.model_dump()
    res = await db.status_columns.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


@router.patch("/{column_id}")
async def update_column(column_id: str, payload: StatusColumnUpdate, _=Depends(require_manager)):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await get_db().status_columns.find_one_and_update(
        {"_id": oid(column_id)}, {"$set": data}, return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Column not found")
    return serialize(res)


@router.delete("/{column_id}", status_code=204)
async def delete_column(column_id: str, _=Depends(require_manager)):
    db = get_db()
    col = await db.status_columns.find_one({"_id": oid(column_id)})
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    if await db.tasks.count_documents({"status": col["key"]}) > 0:
        raise HTTPException(
            status_code=400, detail="Cannot delete a column that still has tasks"
        )
    await db.status_columns.delete_one({"_id": oid(column_id)})
