# Design — Task Move Activity Log

**Date:** 2026-06-26
**Status:** Approved
**Part of:** round-2 batch — (1) Board views + responsive fix, (2) **Task move activity log** ← this doc.

## Overview

Record an audit entry whenever a task changes status (is "moved" between columns), and show each task's move history inside the task modal.

## Goals

- Persist who moved a task, from which status to which, and when.
- Show a per-task move history (newest first) in the task modal.

## Non-Goals

- No logging of non-status edits (title/priority/assignee/etc.).
- No global activity feed in this spec (per-task history only — chosen scope).
- No diff of reordering within the same column (that is not a status change).

## Architecture

### Data
A new MongoDB collection `activity_log`, one document per move:
```json
{ "task_id": "<id>", "task_number": "TASK-12", "action": "move",
  "user_id": "<id>", "username": "peerakia",
  "from_status": "TODO", "to_status": "InProgress", "at": "<iso>" }
```
Index `task_id` for the history query.

### Backend (`app/routers/tasks.py`)
- A helper `_log_move(db, task, from_status, to_status, user)` inserts an `activity_log` doc (skips when `from_status == to_status`).
- Capture the current user in the move paths (these currently discard it via `_=Depends(require_member)`):
  - `PATCH /api/tasks/{id}/move` — log when `payload.status != task.status`.
  - `PATCH /api/tasks/reorder/bulk` — log each item whose status changed.
  - `PATCH /api/tasks/{id}` — log when an edit changes `status` (consistency).
- New endpoint `GET /api/tasks/{task_id}/history` (auth `get_current_user`): returns `activity_log` for the task, sorted by `at` descending.
- `_ensure_indexes` in `database.py`: add `activity_log` index on `task_id` (+ `at`).

### Frontend (`components/TaskModal.vue`)
- For an existing task, fetch `GET /api/tasks/{id}/history` on open and render a **History** section:
  - each row: `{username} moved {from} → {to} · {relative/abs time}`.
  - empty state: "No moves yet."
- New tasks (no id) don't show the section.

## Data Flow
Drag/drop and edits hit the existing move/reorder/update endpoints; those now also append to `activity_log`. The modal reads the log on open. (Move history reflects server truth; the board itself is unchanged.)

## Error Handling / Edge Cases
- Logging failure must not break the move: wrap the insert so a log error is swallowed/logged, the status change still returns success. (Audit is best-effort, not transactional with the move.)
- A task created directly in a non-first column has no "from" — that's a create, not a move, so it is not logged.
- Deleting a task leaves its log rows orphaned; acceptable (history endpoint 404s with the task). Optionally clean up on delete — out of scope.

## Testing
- Backend (`http_test.py`): move a task TODO→InProgress→Done, then `GET /history` and assert two entries in order with correct `from`/`to`/`username`; a same-column reorder adds none; an edit that changes status adds one.
- Frontend: manual — move a task on the board, open it, see the history entries.

## Files Touched
- `backend/app/routers/tasks.py` (`_log_move`, capture user, history endpoint)
- `backend/app/database.py` (activity_log index)
- `backend/tests/http_test.py` (history assertions)
- `frontend/src/components/TaskModal.vue` (History section + fetch)

## Acceptance Criteria
- [ ] Moving a task between columns records who/from/to/when.
- [ ] `GET /api/tasks/{id}/history` returns the task's moves newest-first.
- [ ] The task modal shows the move history for existing tasks; new tasks don't.
- [ ] A same-column reorder records nothing; a logging error never fails the move.
