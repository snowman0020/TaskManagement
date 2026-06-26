# Design — Complete Sprint (delete done tasks) + UTC+7 timestamps

**Date:** 2026-06-26
**Status:** Approved

Two small changes:

## Feature A — Display timestamps in UTC+7

The only wall-clock timestamp shown is the task **Move history** (`TaskModal`), which
currently uses the browser's local timezone. Render it explicitly in **Asia/Bangkok
(UTC+7)** so it's consistent regardless of the viewer's machine.

- Add `frontend/src/utils/datetime.js` with `formatDateTime(iso)` →
  `new Date(iso).toLocaleString('en-GB', { timeZone: 'Asia/Bangkok', hour12: false, … })`.
- Use it in `TaskModal.fmtTime`.
- **Do not** change the Admin sprint date columns — they are date-only values stored at
  UTC midnight; shifting them to +7 would push the end date a day forward. Backend keeps
  storing UTC; the conversion is display-only.

## Feature B — Complete Sprint (Admin) → delete that sprint's done tasks

A manager/admin can "complete" a sprint, which **permanently deletes the sprint's done
tasks** and marks the sprint completed. This is destructive and guarded by a confirm.

### Backend
- `POST /api/sprints/{sprint_id}/complete` (auth `require_manager`):
  - 404 if the sprint doesn't exist.
  - Determine "done" column keys = columns with `is_done = true`; if none are flagged,
    fall back to the last column by order.
  - `delete_many({ sprint_id, status: { $in: done_keys } })` — only tasks **in this
    sprint** whose status is a done column. Backlog and other sprints are untouched.
  - Set the sprint `status = 'completed'`.
  - Return `{ "deleted": <count>, "sprint": <updated sprint> }`.

### Frontend (`Admin.vue`, Sprints tab)
- Add a **Complete** button on each sprint row (next to Delete).
- On click, `confirm("Complete \"<name>\"? This permanently deletes its done tasks and cannot be undone.")`;
  on confirm, `POST .../complete`, then alert the deleted count and reload the list.

### Edge cases
- Sprint with no done tasks → deletes 0, still marks completed (idempotent, harmless).
- Already-completed sprint → completing again just re-runs (deletes any new done tasks).
- Deleting done tasks removes them from dashboard/leadtime metrics — expected (it's a cleanup action).
- Their image attachments (GridFS) become orphaned; acceptable for now (same as normal task delete, which also doesn't purge GridFS) — noted, not addressed here.

### Testing
- Backend (`http_test.py`): create a sprint; add a done task and a non-done task in it,
  plus a done task in the backlog; `POST .../complete`; assert only the in-sprint done
  task is gone, the others remain, and the sprint status is `completed`; assert the
  returned `deleted` count is 1.
- Frontend: manual — Complete a sprint, confirm the dialog, see the done tasks removed
  and the status flip to completed.

## Files Touched
- `frontend/src/utils/datetime.js` (new)
- `frontend/src/components/TaskModal.vue` (use formatter)
- `frontend/src/views/Admin.vue` (Complete button + handler)
- `backend/app/routers/sprints.py` (complete endpoint)
- `backend/tests/http_test.py` (complete-sprint assertions)

## Acceptance Criteria
- [ ] Move-history timestamps display in UTC+7 (Asia/Bangkok).
- [ ] Admin can complete a sprint; it deletes only that sprint's done tasks and sets status=completed.
- [ ] The action is confirmed before deleting and reports how many tasks were removed.
- [ ] Backlog and other sprints' tasks are never touched.
