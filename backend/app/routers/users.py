from fastapi import APIRouter, Depends, HTTPException

from app.core.deps import get_current_user, require_admin
from app.core.security import hash_password
from app.database import get_db
from app.models.user import Role
from app.schemas.common import oid, serialize, serialize_list
from app.schemas.user import UserCreate, UserOut, UserUpdate

router = APIRouter(prefix="/api/users", tags=["users"])


@router.get("", response_model=list[UserOut])
async def list_users(current=Depends(get_current_user)):
    docs = await get_db().users.find().to_list(1000)
    return [UserOut(**serialize(d)) for d in serialize_list(docs)]


@router.post("", response_model=UserOut, status_code=201)
async def create_user(payload: UserCreate, _=Depends(require_admin)):
    db = get_db()
    if await db.users.find_one(
        {"$or": [{"username": payload.username}, {"email": payload.email}]}
    ):
        raise HTTPException(status_code=409, detail="Username or email already exists")
    doc = {
        "username": payload.username,
        "email": payload.email,
        "full_name": payload.full_name,
        "role": payload.role.value,
        "hashed_password": hash_password(payload.password),
        "is_active": True,
    }
    res = await db.users.insert_one(doc)
    doc["_id"] = res.inserted_id
    return UserOut(**serialize(doc))


@router.patch("/{user_id}", response_model=UserOut)
async def update_user(user_id: str, payload: UserUpdate, current=Depends(require_admin)):
    db = get_db()
    update: dict = {}
    data = payload.model_dump(exclude_unset=True)
    if "password" in data and data["password"]:
        update["hashed_password"] = hash_password(data.pop("password"))
    if "role" in data and data["role"] is not None:
        update["role"] = Role(data.pop("role")).value
    update.update({k: v for k, v in data.items() if v is not None})

    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")

    target_id = oid(user_id)
    is_self = str(current["_id"]) == user_id
    demoting = update.get("role") not in (None, Role.ADMIN.value) if "role" in update else False
    deactivating = update.get("is_active") is False

    # Don't let an admin lock themselves out of admin access.
    if is_self and (demoting or deactivating):
        raise HTTPException(
            status_code=400, detail="Cannot change your own role or active status"
        )

    # Don't let the last active admin be demoted or deactivated.
    if demoting or deactivating:
        target = await db.users.find_one({"_id": target_id})
        if (
            target
            and target.get("role") == Role.ADMIN.value
            and target.get("is_active", True)
            and await db.users.count_documents(
                {"role": Role.ADMIN.value, "is_active": True}
            )
            <= 1
        ):
            raise HTTPException(
                status_code=400, detail="Cannot remove the last active admin"
            )

    res = await db.users.find_one_and_update(
        {"_id": target_id}, {"$set": update}, return_document=True
    )
    if not res:
        raise HTTPException(status_code=404, detail="User not found")
    return UserOut(**serialize(res))


@router.delete("/{user_id}", status_code=204)
async def delete_user(user_id: str, current=Depends(require_admin)):
    if str(current["_id"]) == user_id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    res = await get_db().users.delete_one({"_id": oid(user_id)})
    if res.deleted_count == 0:
        raise HTTPException(status_code=404, detail="User not found")
