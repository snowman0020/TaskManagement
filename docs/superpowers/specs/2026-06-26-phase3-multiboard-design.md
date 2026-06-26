# Design — Phase 3: Multi-board (channels) + per-board running number

**Date:** 2026-06-26
**Status:** Approved

The biggest phase. Split into **3a (backend foundation + migration)** and **3b (frontend
switcher + wiring)**. To contain breakage, `board_id` is **optional everywhere** and falls
back to a seeded **Default** board — so existing calls/tests keep working against it.

## Decisions (from clarification)
- A board owns its **tasks, sprints, and status columns**.
- **admin** creates boards and manages members; global roles stay; membership = access to
  that board.
- Migration: seed a **Default** board, backfill all existing data into it, make every user
  a member, and move the global task counter into it.
- Board switcher = a **dropdown in the top bar** (active board persisted in localStorage).
- **Per-board running number**: each board has a `prefix` and its own counter (with a
  configurable start number).

## Data
- New `boards` collection: `{ name, prefix, member_ids: [..], is_default: bool, created_at }`.
- Per-board counter in the existing `counters` collection: `_id = "task:<board_id>"`, `seq`.
  On board create, seed `seq = start_number - 1` so the first task is `start_number`.
- Add `board_id` to `tasks`, `sprints`, `status_columns`.
- Indexes: `tasks.board_id`, `sprints.board_id`, `status_columns.board_id`,
  `boards.member_ids`.

## Board resolution & access (`app/services/access.py`)
- `resolve_board_id(board_id)` → the given id, or the **default** board's id when omitted.
- `ensure_board_access(board_id, user)`:
  - the **default** board is open to every authenticated user (keeps existing flows working);
  - otherwise **admin** passes, and any other user must be in `member_ids`, else **403**;
  - unknown board → **404**.

## 3a — Backend

### boards router (`/api/boards`)
- `GET ""` — boards the user can access (admin → all; others → default + boards they're in).
- `POST ""` (require_admin) — create `{ name, prefix, start_number?, member_ids? }`; seed the
  per-board counter and a default set of status columns for the board.
- `PATCH "/{id}"` (require_admin) — update name / prefix / members.
- `DELETE "/{id}"` (require_admin) — delete the board and its tasks, sprints, columns, and
  counter (the default board cannot be deleted).

### Scoping (optional `board_id`, default fallback + access check)
- `tasks`: `list_tasks`, `board`, `create_task` take `board_id`; reads filter by it; create
  stamps it. Task numbers use the board's `prefix` + per-board counter.
  `_status_context` / status validation is scoped to the task's board.
- `sprints`: `list_sprints`, `create_sprint`, `generate_sprints` take `board_id`.
- `status_columns`: `list_columns`, `create_column`, `reorder` take `board_id`; key
  uniqueness is **per board**.
- `dashboard`: `overview` takes `board_id` and scopes its task metrics.
- `complete_sprint` notifies the **board's members** (falling back to all users for the
  default board).

### Migration (`seed_defaults`)
- Ensure a `Default` board (`is_default=true`, `prefix="TASK"`, all users as members).
- Backfill `board_id` = default on any task/sprint/status_column lacking one.
- Move the legacy global counter `{_id:"task"}` to `{_id:"task:<default>"}`.
- New users are effectively members of the default board (it's open to all).

### Tests (`http_test.py`)
- Existing calls (no `board_id`) keep passing against the default board.
- New: create a second board with a prefix + start number; a task created in it gets
  `<PREFIX>-<start>`; its tasks/columns are isolated from the default board; a non-member
  is denied (403); admin can access any board.

## 3b — Frontend
- A board store (active board id, persisted) + `BoardSwitcher.vue` dropdown in the top bar.
- Thread `board_id` through Board, Admin (columns/sprints), and TaskModal API calls.
- Admin **Boards** tab: create a board (name / prefix / start number) and manage members.

## Acceptance Criteria
- [ ] Existing data lives in a Default board; current flows work unchanged against it.
- [ ] An admin can create a board with its own prefix + start number; its tasks number from there.
- [ ] Tasks / sprints / columns are isolated per board; non-members get 403 on other boards.
- [ ] The top-bar switcher changes the active board and everything scopes to it.
- [ ] Sprint-complete notifications go to the board's members.
