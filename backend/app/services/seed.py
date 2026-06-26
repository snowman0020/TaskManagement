from app.config import settings
from app.core.security import hash_password
from app.database import get_db
from app.models.user import Role

DEFAULT_COLUMNS = [
    {"key": "TODO", "name": "To Do", "order": 0, "wip_limit": None, "is_done": False},
    {"key": "InProgress", "name": "In Progress", "order": 1, "wip_limit": 5, "is_done": False},
    {"key": "QA", "name": "QA", "order": 2, "wip_limit": 3, "is_done": False},
    {"key": "Done", "name": "Done", "order": 3, "wip_limit": None, "is_done": True},
]


async def seed_defaults() -> None:
    db = get_db()

    # Seed default status columns (configurable later via admin page)
    if await db.status_columns.count_documents({}) == 0:
        await db.status_columns.insert_many([dict(c) for c in DEFAULT_COLUMNS])

    # Seed the first admin account
    if await db.users.count_documents({}) == 0:
        await db.users.insert_one(
            {
                "username": settings.admin_username,
                "email": settings.admin_email,
                "full_name": "Administrator",
                "role": Role.ADMIN.value,
                "hashed_password": hash_password(settings.admin_password),
                "is_active": True,
            }
        )
