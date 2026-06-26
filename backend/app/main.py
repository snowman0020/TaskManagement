from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import close_mongo_connection, connect_to_mongo
from app.routers import (
    auth,
    dashboard,
    sprints,
    status_columns,
    task_images,
    tasks,
    users,
)
from app.services.seed import seed_defaults


@asynccontextmanager
async def lifespan(app: FastAPI):
    await connect_to_mongo()
    await seed_defaults()
    yield
    await close_mongo_connection()


app = FastAPI(title="Task Management API", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(tasks.router)
app.include_router(task_images.router)
app.include_router(sprints.router)
app.include_router(status_columns.router)
app.include_router(dashboard.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
