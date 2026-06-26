"""Board resolution and per-board access control.

`board_id` is optional throughout the API; when omitted it resolves to the
seeded Default board, so pre-multi-board callers keep working unchanged.
"""
from fastapi import HTTPException

from app.database import get_db
from app.models.user import Role
from app.schemas.common import oid


async def default_board_id() -> str:
    board = await get_db().boards.find_one({"is_default": True})
    if not board:
        raise HTTPException(status_code=500, detail="Default board not initialised")
    return str(board["_id"])


async def resolve_board_id(board_id: str | None) -> str:
    """Return the given board id, or the default board's id when omitted."""
    return board_id or await default_board_id()


async def ensure_board_access(board_id: str, user: dict) -> dict:
    """Return the board if the user may use it, else raise 403/404.

    The default board is open to every authenticated user; any other board
    requires admin or membership.
    """
    board = await get_db().boards.find_one({"_id": oid(board_id)})
    if not board:
        raise HTTPException(status_code=404, detail="Board not found")
    if board.get("is_default"):
        return board
    if user.get("role") == Role.ADMIN:
        return board
    if str(user["_id"]) in (board.get("member_ids") or []):
        return board
    raise HTTPException(status_code=403, detail="No access to this board")
