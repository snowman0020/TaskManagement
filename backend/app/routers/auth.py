from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm

from app.core.deps import get_current_user
from app.core.security import create_access_token, verify_password
from app.database import get_db
from app.schemas.common import serialize
from app.schemas.user import LoginResponse, UserOut

router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.post("/login", response_model=LoginResponse)
async def login(form: OAuth2PasswordRequestForm = Depends()):
    db = get_db()
    # allow login with username OR email
    user = await db.users.find_one(
        {"$or": [{"username": form.username}, {"email": form.username}]}
    )
    if not user or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
        )
    if not user.get("is_active", True):
        raise HTTPException(status_code=403, detail="User is disabled")

    token = create_access_token(subject=str(user["_id"]), role=user["role"])
    return LoginResponse(access_token=token, user=UserOut(**serialize(user)))


@router.get("/me", response_model=UserOut)
async def me(current=Depends(get_current_user)):
    return UserOut(**serialize(current))
