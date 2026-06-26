from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_manager
from app.database import get_db
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.sprint import (
    StatusColumnCreate,
    StatusColumnReorder,
    StatusColumnUpdate,
)
from app.services.access import ensure_board_access, resolve_board_id

router = APIRouter(prefix="/api/status-columns", tags=["status-columns"])


@router.get("")
async def list_columns(board_id: str | None = None, current=Depends(get_current_user)):
    board_id = await resolve_board_id(board_id)
    await ensure_board_access(board_id, current)
    docs = await get_db().status_columns.find({"board_id": board_id}).sort("order", 1).to_list(100)
    return serialize_list(docs)


@router.post("", status_code=201)
async def create_column(payload: StatusColumnCreate, current=Depends(require_manager)):
    db = get_db()
    board_id = await resolve_board_id(payload.board_id)
    await ensure_board_access(board_id, current)
    if await db.status_columns.find_one({"key": payload.key, "board_id": board_id}):
        raise HTTPException(status_code=409, detail="Column key already exists")
    doc = payload.model_dump()
    doc["board_id"] = board_id
    res = await db.status_columns.insert_one(doc)
    doc["_id"] = res.inserted_id
    return serialize(doc)


# Defined before "/{column_id}" so the literal path isn't captured as an id.
@router.patch("/reorder")
async def reorder_columns(payload: StatusColumnReorder, current=Depends(require_manager)):
    """Persist a new column order after a drag-and-drop in Admin."""
    db = get_db()
    for item in payload.items:
        col = await db.status_columns.find_one({"_id": oid(item.id)})
        if not col:
            continue
        await ensure_board_access(col.get("board_id"), current)
        await db.status_columns.update_one(
            {"_id": oid(item.id)}, {"$set": {"order": item.order}}
        )
    return {"updated": len(payload.items)}


@router.patch("/{column_id}")
async def update_column(column_id: str, payload: StatusColumnUpdate, current=Depends(require_manager)):
    db = get_db()
    col = await db.status_columns.find_one({"_id": oid(column_id)})
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    await ensure_board_access(col.get("board_id"), current)

    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")

    board_id = col.get("board_id")
    old_key = col["key"]
    new_key = data.get("key")
    key_changed = bool(new_key) and new_key != old_key
    if key_changed and await db.status_columns.find_one({"key": new_key, "board_id": board_id}):
        raise HTTPException(status_code=409, detail="Column key already exists")
    if not key_changed:
        data.pop("key", None)  # never write a null/unchanged key over the real one

    res = await db.status_columns.find_one_and_update(
        {"_id": oid(column_id)}, {"$set": data}, return_document=True
    )
    # cascade the rename so this board's tasks on the old status follow the key
    if key_changed:
        await db.tasks.update_many(
            {"status": old_key, "board_id": board_id}, {"$set": {"status": new_key}}
        )
    return serialize(res)


@router.delete("/{column_id}", status_code=204)
async def delete_column(column_id: str, current=Depends(require_manager)):
    db = get_db()
    col = await db.status_columns.find_one({"_id": oid(column_id)})
    if not col:
        raise HTTPException(status_code=404, detail="Column not found")
    await ensure_board_access(col.get("board_id"), current)
    if await db.tasks.count_documents(
        {"status": col["key"], "board_id": col.get("board_id")}
    ) > 0:
        raise HTTPException(
            status_code=400, detail="Cannot delete a column that still has tasks"
        )
    await db.status_columns.delete_one({"_id": oid(column_id)})
