from bson import ObjectId
from bson.errors import InvalidId
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from app.core.security import decode_access_token
from app.database import get_db
from app.models.user import Role

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exc = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    payload = decode_access_token(token)
    if not payload or "sub" not in payload:
        raise credentials_exc

    try:
        user_id = ObjectId(payload["sub"])
    except (InvalidId, TypeError):
        raise credentials_exc

    user = await get_db().users.find_one({"_id": user_id})
    if not user:
        raise credentials_exc
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User is disabled")
    return user


def require_roles(*roles: Role):
    async def checker(user: dict = Depends(get_current_user)) -> dict:
        if user.get("role") not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient permissions",
            )
        return user

    return checker


require_admin = require_roles(Role.ADMIN)
require_manager = require_roles(Role.ADMIN, Role.MANAGER)
