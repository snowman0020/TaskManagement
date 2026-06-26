# Design — Board Assignee Filter + Sprint Manday

**Date:** 2026-06-26
**Status:** Approved (pending written-spec review)
**Part of:** a 3-spec batch — (1) UI Shell, (2) Task Image Attachments, (3) **Board Filter + Sprint Manday** ← this doc. Build order: 1 → 2 → 3. Two small, independent features grouped because each is a thin slice (one endpoint/schema change + one view).

---

## Feature D — Board Assignee Filter

### Overview
On the Board page, show the list of users so you can filter the board to one person's tasks (see other people's work), in addition to the existing sprint filter.

### Goals
- Filter the board by assignee from the Board page.
- Quick "All" and "Me" shortcuts; also "Unassigned".

### Non-Goals
- No multi-select (one assignee at a time, plus All/Unassigned).
- No saved/remembered filter across sessions (keep it in-page state).

### Backend
- `GET /api/tasks/board` (`app/routers/tasks.py`) gains an optional `assignee_id: str | None = Query(None)`.
  - When present, add `assignee_id` to the task query (alongside the existing optional `sprint_id`).
  - Special value handling: `assignee_id="none"` (or an explicit `unassigned` flag) filters tasks where `assignee_id` is null/absent, so "Unassigned" works. (Pick one convention and document it; recommended: a literal `"none"` sentinel querying `{"assignee_id": None}`.)
- `list_tasks` already supports `assignee_id`; the board endpoint mirrors it. No schema/model change.

### Frontend (`src/views/Board.vue`)
- Add a horizontal **avatar-chip filter row** above the board:
  - chips: `All` · `Me` (current user) · one chip per user (avatar initials + name on hover) · `Unassigned`.
  - The active chip is highlighted.
  - Selecting a chip sets `selectedAssignee` and re-fetches the board (`loadBoard()` passes `assignee_id` in params; `"none"` for Unassigned, omitted for All, the user id otherwise).
- Reuse the existing `users` list already loaded in `loadMeta()` and the existing `initials()` / `userMap` helpers.
- Combine with the sprint filter (both params sent together).

### Edge Cases
- Many users → the chip row scrolls horizontally (consistent with the mobile board scroll from Spec 1).
- A user is deleted while selected → board returns empty; "All" resets it.

### Testing
- Backend: extend `tests/http_test.py` — create tasks with different `assignee_id`, assert `GET /api/tasks/board?assignee_id=<id>` returns only that user's tasks, and the `"none"` sentinel returns unassigned tasks.
- Frontend: manual + Playwright — select a user chip, confirm the board shows only their cards; "All" restores; "Unassigned" works.

---

## Feature E — Sprint Manday

### Overview
Let a manager set a **manday** value (planned capacity in man-days) on each sprint.

### Goals
- Store and edit a `manday` number per sprint.
- Set it when generating sprints (optional default applied to the batch) and edit it per sprint afterward.
- Display it in the Admin sprints table.

### Non-Goals
- No automatic computation from team size/velocity (manager enters it manually).
- No capacity-vs-committed analytics in this spec (a `manday` field is stored and shown; dashboards can consume it later).

### Backend (`app/schemas/sprint.py`, `app/routers/sprints.py`)
- Add `manday: float | None = None` to:
  - `SprintCreate` — persisted on create.
  - `SprintUpdate` — editable via the existing `PATCH /api/sprints/{id}` (which already does a generic `$set` from `model_dump(exclude_unset=True)`, so adding the field to the schema is sufficient; confirm `None` vs omitted semantics — omitted leaves it unchanged).
  - `SprintGenerate` — optional `manday` applied to every generated sprint in the batch.
- `build_sprints` / `create_sprint` write `manday` into the sprint document (default `None`).
- Validation: `manday` must be `>= 0` when provided (`Field(ge=0)`).

### Frontend (`src/views/Admin.vue`, Sprints tab)
- Generate form: add an optional `Manday (default)` number input bound into the `gen` payload.
- Sprints table: add a **Manday** column with an editable `<input type="number" min="0">` per row and a **Save** button that `PATCH`es `{ manday }`. (Currently sprint rows only expose a status select and delete; this adds a small save action — keep it row-scoped like the Status Columns tab does.)
- Show `manday` (and keep `working_days`) in the table.

### Edge Cases
- Empty input → send `null` (clears/leaves unset), not `0`, to distinguish "not set" from "zero capacity".
- Non-numeric input prevented by the number input + server `ge=0` guard.

### Testing
- Backend: extend `tests/http_test.py` — create a sprint with `manday`, assert it round-trips; `PATCH` updates it; `generate` with a default `manday` stamps all created sprints; negative `manday` rejected `422`.
- Frontend: manual — set manday on a sprint, reload, confirm it persisted.

---

## Files Touched

- `backend/app/routers/tasks.py` (board `assignee_id` param)
- `backend/app/schemas/sprint.py` (`manday` on create/update/generate)
- `backend/app/routers/sprints.py` + `services/sprint_service.py` (persist `manday`)
- `backend/tests/http_test.py` (board filter + manday assertions)
- `frontend/src/views/Board.vue` (assignee chip filter row)
- `frontend/src/views/Admin.vue` (manday input + per-row save, generate default)

## Acceptance Criteria

- [ ] Board can be filtered by a chosen user, by "Me", by "Unassigned", and reset with "All".
- [ ] The board endpoint filters by `assignee_id` (and the unassigned sentinel) combined with the sprint filter.
- [ ] A manager can set/edit `manday` per sprint and on generate; it persists and shows in Admin.
- [ ] Negative manday rejected; empty leaves it unset.
- [ ] Existing tests still pass; new assertions added to `http_test.py`.
