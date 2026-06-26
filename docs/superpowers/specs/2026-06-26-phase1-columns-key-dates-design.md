# Design — Phase 1: column reorder + editable key + expected date + DatePicker

**Date:** 2026-06-26
**Status:** Approved

First phase of a 3-phase batch. Phase 2 = task comments/replies; Phase 3 = multi-board
(channels) + per-board membership (each gets its own design round). This phase is the
small, low-risk UI/field changes that don't touch the architecture.

## #1 — Drag to reorder status columns (Admin)

- **Frontend** (`Admin.vue`, Status Columns table): make the rows draggable with
  `vuedraggable` (already a dependency), rendered as `<draggable tag="tbody">`. A drag
  handle cell starts the drag. On drop, set each column's `order` to its new index and
  persist.
- **Backend** (`status_columns.py`): new `PATCH /api/status-columns/reorder` (auth
  `require_manager`) taking `{ items: [{ id, order }] }`, writing each `order`. Defined
  **before** the `/{column_id}` route so the literal path isn't captured as an id.
- The board already renders columns sorted by `order`, so reordering here reorders the
  board columns too.

## #2 — Edit a column's KEY (with cascade)

- **Backend**: add `key` (optional, 1–40 chars) to `StatusColumnUpdate`. In
  `update_column`, when the key changes:
  - reject if the new key already exists (409),
  - update the column,
  - **cascade**: `tasks.update_many({ status: old_key }, { $set: { status: new_key } })`
    so no task is left pointing at a dead status.
- **Frontend**: the key cell becomes an editable input; `saveColumn` includes `key` in
  the PATCH (sending the same key is a no-op — cascade only runs on an actual change).

## #6 — "Expected date" on a task

- The task model already has `due_date` (a `datetime`), but it isn't shown in the UI.
  Surface it in `TaskModal` as a date field **labeled "Expected date"** bound to
  `form.due_date`. No new field — reuse `due_date`.
- Convert between the stored ISO datetime and the `YYYY-MM-DD` the date input expects;
  send the date string on save (the backend's `datetime` field parses it). Empty → `null`.
- Also show a small `📅 <date>` badge on the board card when a task has a date.

## #7 — DatePicker on every date input

- Add a reusable `components/DateField.vue` that wraps a native `<input type="date">`
  (which is itself a calendar picker — no new dependency) and normalizes the value
  (accepts an ISO datetime or a date string, emits `YYYY-MM-DD` or `null`).
- Use it for every date input: the Admin "generate sprints" start date and the new task
  Expected date. This standardizes date handling and guarantees a picker everywhere.
- (If a richer JS datepicker library is wanted later, `DateField` is the single place to
  swap the implementation.)

## Testing
- Backend (`http_test.py`): reorder columns and assert the new `order`; rename a column's
  key that has tasks and assert the tasks' `status` cascaded to the new key and the old
  key is gone; renaming to an existing key returns 409.
- Frontend: manual + Playwright — drag a column to reorder, edit a key, set an Expected
  date and confirm it persists, and confirm the date inputs show a calendar picker.

## Files Touched
- `backend/app/schemas/sprint.py` (`StatusColumnUpdate.key`, reorder schema)
- `backend/app/routers/status_columns.py` (reorder endpoint, key cascade)
- `backend/tests/http_test.py`
- `frontend/src/components/DateField.vue` (new)
- `frontend/src/views/Admin.vue` (draggable rows, editable key, DateField)
- `frontend/src/components/TaskModal.vue` (Expected date via DateField)
- `frontend/src/views/Board.vue` (date badge on card)

## Acceptance Criteria
- [ ] Admin can drag status columns to reorder; the order persists and the board reflects it.
- [ ] Admin can edit a column key; existing tasks on that column follow the rename; duplicate keys are rejected.
- [ ] A task's Expected date can be set/cleared and persists; it shows on the card.
- [ ] All date inputs present a calendar picker via the shared `DateField`.
