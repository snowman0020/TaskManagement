from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response

from app.core.deps import get_current_user, require_admin
from app.database import get_db
from app.models.user import Role
from app.schemas.board import BoardCreate, BoardUpdate
from app.schemas.common import oid, serialize, serialize_list
from app.services.seed import DEFAULT_COLUMNS

router = APIRouter(prefix="/api/boards", tags=["boards"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


@router.get("")
async def list_boards(current=Depends(get_current_user)):
    """Boards the user may use: admins see all; others see the default + theirs."""
    db = get_db()
    if current.get("role") == Role.ADMIN:
        docs = await db.boards.find().sort("created_at", 1).to_list(500)
    else:
        uid = str(current["_id"])
        docs = await db.boards.find(
            {"$or": [{"is_default": True}, {"member_ids": uid}]}
        ).sort("created_at", 1).to_list(500)
    return serialize_list(docs)


@router.post("", status_code=201)
async def create_board(payload: BoardCreate, _=Depends(require_admin)):
    db = get_db()
    doc = {
        "name": payload.name,
        "prefix": payload.prefix,
        "member_ids": payload.member_ids,
        "is_default": False,
        "created_at": _now(),
    }
    res = await db.boards.insert_one(doc)
    board_id = str(res.inserted_id)
    doc["_id"] = res.inserted_id

    # seed the per-board running-number counter so the first task = start_number
    await db.counters.update_one(
        {"_id": f"task:{board_id}"},
        {"$set": {"seq": payload.start_number - 1}},
        upsert=True,
    )
    # seed a default set of status columns for the new board
    await db.status_columns.insert_many(
        [{**dict(c), "board_id": board_id} for c in DEFAULT_COLUMNS]
    )
    return serialize(doc)


@router.patch("/{board_id}")
async def update_board(board_id: str, payload: BoardUpdate, _=Depends(require_admin)):
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise HTTPException(status_code=400, detail="Nothing to update")
    res = await get_db().boards.find_one_and_update(
        {"_id": oid(board_id)}, {"$set": data}, return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="Board not found")
    return serialize(res)


@router.delete("/{board_id}", status_code=204)
async def delete_board(board_id: str, _=Depends(require_admin)):
    db = get_db()
    board = await db.boards.find_one({"_id": oid(board_id)})
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete the default board")
    # cascade: remove the board's tasks, sprints, columns, and counter
    await db.tasks.delete_many({"board_id": board_id})
    await db.sprints.delete_many({"board_id": board_id})
    await db.status_columns.delete_many({"board_id": board_id})
    await db.counters.delete_one({"_id": f"task:{board_id}"})
    await db.boards.delete_one({"_id": oid(board_id)})
    return Response(status_code=204)
