# Design — Board Views (Active/Backlog/All) + Responsive Fix

**Date:** 2026-06-26
**Status:** Approved
**Part of:** round-2 batch — (1) **Board views + responsive fix** ← this doc, (2) Task move activity log. A one-off data seed (10 backlog tasks for `peerakia`) runs before this spec so the views have data to show.

## Overview

Two board/layout changes bundled because they share `Board.vue` / `AppLayout.vue` / `main.css`:

- **Responsive fix (bug):** resizing a desktop window (sidebar open) down to mobile width makes the off-canvas drawer auto-open and cover the content. Fix the breakpoint transition.
- **Board view toggle:** a segmented control to switch the board between the **Active Sprint**, the **Backlog**, and **All**.

## Part A — Responsive fix

### Problem
`AppLayout` uses one `sidebarOpen` state for both the desktop docked panel and the mobile drawer. On desktop `open = true` is normal; when the viewport crosses to ≤768px, that same `true` renders as an open drawer + backdrop over the content (reproduced via resize).

### Fix
Add a `matchMedia('(max-width: 768px)')` listener in `AppLayout`:
- On change **into** mobile (`matches === true`): set `sidebarOpen = false` (drawer starts closed).
- On change **out of** mobile (`matches === false`): restore the saved desktop preference (`savedOpen()`).

Keep the existing route-change close on mobile. Register the listener in `onMounted`, remove it in `onUnmounted`. Wrap `matchMedia` in try/catch (older browsers).

### Acceptance
- Resizing desktop↔mobile never leaves the drawer covering content; entering mobile starts closed; returning to desktop restores the remembered docked state.

## Part B — Board view toggle

### Concept
"Active sprint" = the sprint whose `status === 'active'`. The board gets a segmented control above it:

`[ Active Sprint ] [ Backlog ] [ All ]`

- **Active Sprint** → show tasks in the active sprint. If no sprint is active, show an empty board with a hint ("No active sprint — set one in Admin").
- **Backlog** → tasks with no sprint.
- **All** → no sprint filter.

The existing sprint `<select>` stays as a way to jump to a *specific* named sprint (selecting one switches the mode to that sprint id and the toggle de-highlights). The assignee chip filter (already shipped) keeps working alongside, combined in the same request. Default mode on load: **Active Sprint** if one is active, otherwise **All**.

### Backend
`GET /api/tasks/board` already accepts `sprint_id`. Add a **backlog sentinel**: `sprint_id="none"` → query `{"sprint_id": None}` (matches null/missing), mirroring the existing `assignee_id="none"` convention. No model change.

### Frontend (`Board.vue`)
- `view` ref holds the current mode: `'active' | 'backlog' | 'all' | <sprintId>`.
- `activeSprint` = `sprints.find(s => s.status === 'active')` (computed).
- `loadBoard()` maps the mode to params:
  - `active` → `sprint_id = activeSprint?.id` (if none, set a `noActiveSprint` flag and skip/empty),
  - `backlog` → `sprint_id = 'none'`,
  - `all` → omit,
  - `<sprintId>` → `sprint_id = that id`.
  - plus `assignee_id` from the chip filter when set.
- Segmented control buttons set `view` and re-fetch; the sprint `<select>` sets `view` to the chosen id (or back to a mode).
- When `view === 'active'` and there is no active sprint, render a hint instead of columns.

### Edge cases
- Multiple sprints marked active → use the first by start_date (sprints are returned sorted). Documented; the UI still works.
- Creating a task while in Backlog/Active view: keep current behavior (new task inherits the selected specific sprint only when one is chosen; backlog/all/active-with-id behave sensibly — when an active sprint is selected, default the new task into it).

### Testing
- Backend: extend `http_test.py` — assert `GET /api/tasks/board?sprint_id=none` returns only sprint-less tasks; a task assigned to a sprint is excluded.
- Frontend: manual + Playwright — toggle Active/Backlog/All and confirm the column contents change; reproduce the old resize bug is gone (resize desktop→mobile leaves the drawer closed).

## Files Touched
- `frontend/src/views/AppLayout.vue` (matchMedia listener)
- `frontend/src/views/Board.vue` (view toggle, activeSprint, loadBoard mapping)
- `frontend/src/assets/main.css` (segmented-control styles if needed)
- `backend/app/routers/tasks.py` (backlog sentinel)
- `backend/tests/http_test.py` (backlog filter assertion)

## Acceptance Criteria
- [ ] Resizing across the 768px breakpoint no longer pops the drawer over content.
- [ ] Board toggle switches between Active Sprint, Backlog, and All; the specific-sprint dropdown still works; assignee chips combine.
- [ ] "No active sprint" state shows a hint, not a broken/empty-looking board.
- [ ] Backlog view shows only sprint-less tasks (backed by the `sprint_id=none` sentinel).
