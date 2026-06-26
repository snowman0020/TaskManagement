# Design — Task Image Attachments (multiple images per task)

**Date:** 2026-06-26
**Status:** Approved (pending written-spec review)
**Part of:** a 3-spec batch — (1) UI Shell, (2) **Task Image Attachments** ← this doc, (3) Board Filter + Sprint Manday. Build order: 1 → 2 → 3.

## Overview

Let users attach **more than one image** to a task, on both the New Task and Edit Task flows (they share `TaskModal.vue`). Images display as thumbnails in the modal, can be removed, and a small badge on each board card shows the attachment count. Images are stored in MongoDB GridFS (the stack has no other storage and runs on Docker; GridFS persists with the existing mongo volume and adds no new infrastructure).

## Goals

- Attach 1..N images when creating or editing a task.
- View attached images (thumbnails) in the modal; open/preview full size.
- Remove individual images.
- Board card shows a `📎 N` badge when a task has images.

## Non-Goals

- No non-image attachments (PDF, docs).
- No server-side thumbnail generation/resizing — the browser scales the original via CSS (acceptable at ≤5MB, ≤10 images for an internal tool).
- No drag-to-reorder of images.
- No image editing/cropping.

## Constraints (validated on both client and server)

- Max **10** images per task (existing + newly added combined).
- Max **5 MB** per image.
- Allowed types: **PNG, JPEG, WebP, GIF** — checked by both declared content-type **and** a magic-byte signature sniff (to reject a spoofed content-type).

## Architecture

### Storage
- A GridFS bucket named `task_images` via `motor`'s `AsyncIOMotorGridFSBucket(get_db())`.
- Each task document gains an `images` array; each entry:
  ```json
  { "id": "<gridfs_file_id str>", "filename": "...", "content_type": "image/png",
    "size": 12345, "uploaded_by": "<user_id>", "uploaded_at": "<iso>" }
  ```
  `id` is the GridFS file `ObjectId` rendered as a string (so the existing `serialize()` — which only stringifies top-level ObjectIds — does not need to recurse into the array).

### Backend API — new router `app/routers/task_images.py`, prefix `/api/tasks/{task_id}/images`
- `POST ""` — auth `require_member`. Body: multipart form, field `files` accepting one or many `UploadFile`.
  - Validate: task exists; `(len(existing) + len(incoming)) <= 10`; each file `size <= 5MB`; declared content-type in the allow-list; magic-byte sniff matches an allowed image type.
  - Validate **all** files first; only if all pass, stream each into GridFS (with metadata: `task_id`, `content_type`, `filename`, `uploaded_by`). Append the refs to `task.images` via `$push`/`$each`. On a storage error mid-batch, delete any files already written in this batch (best-effort cleanup) and return 500.
  - Returns the updated `images` array.
- `GET "/{image_id}"` — auth `get_current_user`. Streams the bytes from GridFS as a `StreamingResponse` with the stored `Content-Type`. (Served to the SPA via an authenticated blob fetch — see Frontend.)
- `DELETE "/{image_id}"` — auth `require_member`. Deletes the file from the GridFS bucket and `$pull`s the ref from `task.images`. 404 if the task or image ref is absent.
- Register the router in `app/main.py`.
- `app/schemas/task.py`: add an `ImageMeta` model documenting the array entry shape. `TaskCreate` / `TaskUpdate` are unchanged — images attach **after** the task exists.

### Frontend
- New component `src/components/ImageUploader.vue` used inside `TaskModal.vue`:
  - A drag-and-drop zone plus `<input type="file" multiple accept="image/png,image/jpeg,image/webp,image/gif">`.
  - State: `existingImages` (from `task.images`) and `pendingFiles` (`File[]` chosen but not yet uploaded, previewed via `URL.createObjectURL`).
  - Client-side validation mirrors the server (count, per-file size, type) with an inline error message; invalid files are rejected with a reason, never silently dropped.
  - Thumbnail grid. **Existing** images are fetched as authenticated blobs (`client.get(url, { responseType: 'blob' })` → `URL.createObjectURL`) because a plain `<img src>` cannot send the `Authorization: Bearer` header the API requires. Object URLs are revoked on unmount to avoid leaks.
  - Each thumbnail has a remove (`×`) control:
    - existing image → call `DELETE` immediately (the task already exists; mirrors how task delete works immediately elsewhere).
    - pending file → just remove it from the local array.
- `src/api/client.js`: add a small helper for blob GETs if convenient (otherwise call inline with `responseType: 'blob'`).
- `TaskModal.vue` exposes the selected `pendingFiles` to the parent (`Board.vue`) so the save flow can upload them once a task id exists.
- `Board.vue` `saveTask(payload, pendingFiles)`:
  - **new task:** `POST /api/tasks` → take `id` from the response → `POST /api/tasks/{id}/images` with the pending files → `loadBoard()`.
  - **edit task:** `PATCH /api/tasks/{id}` → upload any pending files → `loadBoard()`.
- Board card (`Board.vue` template): show a `📎 {{ element.images.length }}` badge in `.meta` when `images?.length`.

## Data Flow

Create/update task (JSON) and image upload (multipart) are **separate** requests. The modal collects images locally; the parent orchestrates "create/patch, then upload". Reads stream from GridFS through the authenticated GET, surfaced in the UI via blob object URLs.

## Error Handling / Edge Cases

- Over count / oversize / bad type → `400` with a clear `detail`; the FE keeps the modal open, shows the message, and preserves other field input.
- Magic-byte mismatch (spoofed content-type) → rejected `400`.
- Partial batch storage failure → best-effort cleanup of this batch's already-written files; `500`.
- Deleting an image that is already gone → `404` (idempotent enough; FE refreshes).
- New-task flow where task creation succeeds but image upload fails → the task exists without images; surface the upload error and let the user retry attaching from the (now editable) task. (Documented behavior, not a silent loss.)

## Testing

- `mongomock-motor` (used by the existing `tests/http_test.py`) does **not** implement GridFS, so image-storage tests run against the **real** `tm-mongo` in a new `backend/tests/images_test.py`:
  - login → create task → upload 2 images → assert `task.images` length 2 → `GET` an image and assert non-empty bytes + correct content-type → upload exceeding 10 rejected `400` → oversize rejected `400` → bad type / spoofed content-type rejected `400` → delete one → length 1 → auth required (no token → 401, viewer → 403 on upload/delete).
  - The file cleans up its test DB/bucket at the end.
- Pure validation (count/size/type/magic-byte) factored into a helper and unit-tested without storage.
- **Frontend:** manual + Playwright — open New Task, attach 2 images, save, reopen the created task, confirm 2 thumbnails render, delete 1, confirm count badge on the card updates.

## Files Touched

- `backend/app/routers/task_images.py` (new)
- `backend/app/main.py` (register router)
- `backend/app/schemas/task.py` (`ImageMeta`)
- `backend/app/services/` — optional small validation helper module (or inline in the router)
- `backend/tests/images_test.py` (new)
- `frontend/src/components/ImageUploader.vue` (new)
- `frontend/src/components/TaskModal.vue` (embed uploader, expose pending files)
- `frontend/src/views/Board.vue` (save orchestration, card badge)
- `frontend/src/api/client.js` (optional blob helper)

## Acceptance Criteria

- [ ] Can attach multiple images when creating a task; all are stored and visible after save.
- [ ] Can add and remove images on an existing task.
- [ ] Server rejects >10 images, >5MB files, and non-image/spoofed types with a clear message; the client blocks them too.
- [ ] Images render in the modal using authenticated requests (no public/unauthenticated image URL).
- [ ] Board card shows the attachment count.
- [ ] `backend/tests/images_test.py` passes against `tm-mongo`; existing `http_test.py`/`smoke_test.py` still pass.
