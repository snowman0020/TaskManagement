# Design — Phase 2: Task comments + replies

**Date:** 2026-06-26
**Status:** Approved

Phase 2 of the multi-phase batch. Phase 1 (column reorder / key / dates) is done.
Phase 2.5 = notifications (task move / assign / sprint complete). Phase 3 = multi-board
(channels) + per-board membership + **per-board running number (prefix + start)**.

## Overview

Let users comment on a task and reply to a comment (one level of threading). Comments
show in the task modal.

## Data

A `comments` collection, one document per comment or reply:
```json
{ "task_id": "<id>", "user_id": "<id>", "username": "peerakia",
  "body": "...", "parent_id": null | "<top-comment id>", "created_at": "<iso utc>" }
```
- `parent_id = null` → a top-level comment; otherwise a reply to that top-level comment.
- **One level only**: replying to a reply is rejected.
- Index `(task_id, created_at)`.

## Backend — new router `app/routers/comments.py`, prefix `/api/tasks/{task_id}/comments`
- `GET ""` (auth `get_current_user`): returns the task's comments **nested** —
  `[{ ...comment, replies: [ ...reply ] }]`, top-level sorted by `created_at` ascending,
  replies sorted within each.
- `POST ""` (auth `require_member`): body `{ body, parent_id? }`.
  - `body` required (1–5000 chars).
  - If `parent_id` is given it must be an existing **top-level** comment on this task,
    else 400 (this rejects reply-to-reply and cross-task parents).
  - Stores `created_at` in UTC.
- `DELETE "/{comment_id}"` (auth `require_member`): allowed only for the **author** or an
  **admin/manager** (else 403). Deleting a top-level comment also deletes its replies.
- Register the router in `app/main.py`; add the `comments` index in `database.py`.
- Schema `CommentCreate { body, parent_id? }` (new `app/schemas/comment.py`).

## Frontend — `components/TaskComments.vue` (used in `TaskModal`, existing tasks only)
- On open, `GET` the comments and render:
  - each top-level comment: author, body, timestamp (UTC+7 via the shared
    `formatDateTime`), a **Reply** toggle, and a `×` delete for the author / managers;
  - its replies indented beneath it (same controls, no further Reply);
  - an "Add a comment" input at the bottom; the Reply toggle opens an inline reply input.
- Posting or deleting refetches the list.
- Uses the auth store for the current user id + role to decide which `×` to show.

## Permissions
- member/manager/admin can add comments and replies, and delete their own.
- admin/manager can delete any comment.
- viewer is read-only (can read; `POST`/`DELETE` return 403 via `require_member`).

## Error Handling / Edge Cases
- Empty body → 422 (schema min length).
- Reply to a reply / parent on another task → 400.
- Deleting an already-gone comment → 404.
- Deleting a top-level comment cascades to its replies (no orphaned replies).

## Testing
- Backend (`http_test.py`): post a comment then a reply; `GET` returns the nested shape
  with the reply under its parent; replying to a reply is rejected (400); a viewer is
  blocked (403); the author and an admin can delete; deleting a top-level comment removes
  its replies.
- Frontend: manual — add a comment, reply to it, delete own, confirm threading and times.

## Files Touched
- `backend/app/schemas/comment.py` (new)
- `backend/app/routers/comments.py` (new)
- `backend/app/main.py` (register router)
- `backend/app/database.py` (comments index)
- `backend/tests/http_test.py`
- `frontend/src/components/TaskComments.vue` (new)
- `frontend/src/components/TaskModal.vue` (embed comments)

## Acceptance Criteria
- [ ] A user can comment on a task and reply to a comment (one level).
- [ ] Comments render nested with author and UTC+7 time in the modal.
- [ ] Authors can delete their own comments; managers/admins can delete any; viewers can't post.
- [ ] Deleting a top-level comment removes its replies; reply-to-reply is rejected.
