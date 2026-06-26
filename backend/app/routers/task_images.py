from datetime import datetime, timezone

from bson import ObjectId
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

from app.core.deps import get_current_user, require_member
from app.database import get_db
from app.schemas.common import oid
from app.services.image_validation import (
    MAX_IMAGES_PER_TASK,
    validate_image,
)

router = APIRouter(prefix="/api/tasks/{task_id}/images", tags=["task-images"])

BUCKET_NAME = "task_images"


def _bucket() -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(get_db(), bucket_name=BUCKET_NAME)


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _get_task_or_404(task_id: str) -> dict:
    task = await get_db().tasks.find_one({"_id": oid(task_id)})
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


@router.post("", status_code=201)
async def upload_images(
    task_id: str,
    files: list[UploadFile] = File(...),
    current=Depends(require_member),
):
    db = get_db()
    task = await _get_task_or_404(task_id)
    existing = task.get("images", []) or []

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    # Read + validate every file BEFORE writing any, so a bad file in the batch
    # doesn't leave a half-applied upload.
    prepared: list[tuple[UploadFile, bytes, str]] = []
    for f in files:
        data = await f.read()
        try:
            content_type = validate_image(f.filename or "image", f.content_type, data)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        prepared.append((f, data, content_type))

    if len(existing) + len(prepared) > MAX_IMAGES_PER_TASK:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Too many images: {len(existing)} attached + {len(prepared)} new "
                f"exceeds the limit of {MAX_IMAGES_PER_TASK}"
            ),
        )

    bucket = _bucket()
    written_ids: list[ObjectId] = []
    new_refs: list[dict] = []
    try:
        for f, data, content_type in prepared:
            file_id = await bucket.upload_from_stream(
                f.filename or "image",
                data,
                metadata={
                    "task_id": task_id,
                    "content_type": content_type,
                    "uploaded_by": str(current["_id"]),
                },
            )
            written_ids.append(file_id)
            new_refs.append(
                {
                    "id": str(file_id),
                    "filename": f.filename or "image",
                    "content_type": content_type,
                    "size": len(data),
                    "uploaded_by": str(current["_id"]),
                    "uploaded_at": _now(),
                }
            )
    except Exception:
        # best-effort cleanup of anything written in this failed batch
        for fid in written_ids:
            try:
                await bucket.delete(fid)
            except Exception:
                pass
        raise HTTPException(status_code=500, detail="Failed to store images")

    await db.tasks.update_one(
        {"_id": oid(task_id)}, {"$push": {"images": {"$each": new_refs}}}
    )
    task = await _get_task_or_404(task_id)
    return {"images": task.get("images", [])}


@router.get("/{image_id}")
async def get_image(task_id: str, image_id: str, _=Depends(get_current_user)):
    bucket = _bucket()
    try:
        grid_out = await bucket.open_download_stream(oid(image_id))
    except Exception:
        raise HTTPException(status_code=404, detail="Image not found")
    data = await grid_out.read()
    content_type = "application/octet-stream"
    if grid_out.metadata:
        content_type = grid_out.metadata.get("content_type", content_type)
    return Response(content=data, media_type=content_type)


@router.delete("/{image_id}", status_code=204)
async def delete_image(
    task_id: str, image_id: str, _=Depends(require_member)
):
    db = get_db()
    await _get_task_or_404(task_id)
    bucket = _bucket()
    try:
        await bucket.delete(oid(image_id))
    except Exception:
        # already gone in GridFS — still drop the ref below
        pass
    res = await db.tasks.update_one(
        {"_id": oid(task_id)}, {"$pull": {"images": {"id": image_id}}}
    )
    if res.modified_count == 0:
        raise HTTPException(status_code=404, detail="Image not found on task")
    return Response(status_code=204)
