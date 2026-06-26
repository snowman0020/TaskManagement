# Design — UI Shell: Dark Mode, Responsive, Collapsible Sidebar

**Date:** 2026-06-26
**Status:** Approved (pending written-spec review)
**Part of:** a 3-spec batch — (1) **UI Shell** ← this doc, (2) Task Image Attachments, (3) Board Filter + Sprint Manday. Build order: 1 → 2 → 3. This spec is foundational because it touches the global stylesheet and app layout that the later specs build on.

## Overview

Make the TaskFlow frontend themeable (light/dark) and usable on phones, and let the user collapse/hide the sidebar via a hamburger control. All three concerns are bundled because they share the same two files (`src/assets/main.css`, `src/views/AppLayout.vue`).

## Goals

- Light/dark theme with a manual toggle that persists, defaulting to the OS preference on first visit.
- Layout works down to ~375px wide: the board scrolls horizontally, the sidebar becomes an overlay drawer, page headers stack.
- A hamburger control toggles the sidebar on every viewport — collapsible panel on desktop (state remembered), overlay drawer on mobile.

## Non-Goals

- No per-component scoped styles refactor beyond what theming requires.
- No design-token system / CSS framework introduction. Keep the single global stylesheet + CSS variables.
- No theme beyond light/dark (no custom accent colors).

## Architecture

### Theming
- A small composable `src/composables/useTheme.js` owns theme state:
  - Initial value: `localStorage.getItem('theme')` if present, else `window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'`.
  - Applies the theme by setting `document.documentElement.dataset.theme` (`<html data-theme="dark">`).
  - `setTheme(v)` / `toggle()` persist to `localStorage.theme`.
  - Subscribes to the `matchMedia` change event and follows the OS **only while the user has not made a manual choice** (i.e. no `localStorage.theme` yet). Once the user toggles, the saved choice wins.
  - Exposes a reactive `theme` ref so the toggle icon stays in sync.
- Initialized once at app start (in `main.js` or `App.vue` setup) so the correct theme is applied before first paint where possible.

### CSS refactor (`src/assets/main.css`)
- Promote the remaining hardcoded colors to CSS variables so dark mode can override them in one place:
  - `#ffffff` surfaces (button text stays `#fff`; surfaces → `--panel` / a new `--surface`), input background `#fff` → `--input-bg`.
  - `#ebecf0` (column background, ghost-button hover, default badge) → `--col-bg` / `--chip-bg`.
  - `#e9f2ff` (active nav) → `--nav-active-bg`.
  - shadow `rgba(9,30,66,.2)` → `--shadow`; modal backdrop `rgba(9,30,66,.54)` → `--backdrop`.
  - `#de350b` (danger/error/wip-warn) → `--danger`.
- Add a `[data-theme="dark"]` block overriding the palette: dark `--bg`, `--panel`/`--surface`, `--col-bg`, `--border`, `--text`, `--muted`, `--input-bg`, `--nav-active-bg`, `--shadow`, `--backdrop`.
- Priority/status badge hues (`.badge.low/medium/high/critical`) keep their semantic colors but get dark-mode variants tuned for contrast (darker translucent backgrounds, lighter text) so they remain readable on a dark surface.
- Target: WCAG AA contrast for text on both themes.

### Layout & responsiveness (`src/views/AppLayout.vue` + CSS)
- Introduce a single reactive `sidebarOpen` state plus a hamburger (`☰`) button.
- A persistent top bar holds the hamburger, the `📋 TaskFlow` brand, and the theme toggle. (Brand text is what the user refers to as "TaskFlow" being hideable — collapsing the sidebar hides the nav panel; the brand remains in the top bar.)
- **Desktop (> 768px):** sidebar is a normal docked panel, open by default. Hamburger collapses it; `main` reflows to full width. Collapsed/open state persisted in `localStorage.sidebarOpen`.
- **Mobile (≤ 768px):** sidebar is hidden by default and rendered as an off-canvas drawer (slide-in from the left) with a dimmed backdrop. Opening is via the hamburger; it closes on backdrop click and on route navigation. The drawer reuses the existing nav links, user box, theme toggle, and logout.
- **Board** (`src/views/Board.vue` markup unchanged; CSS only): keep the horizontal flex layout, ensure `overflow-x: auto` with momentum scroll and `scroll-snap-type: x` on small screens; columns shrink to `min(78vw, 280px)` so one column is comfortably visible with the next peeking.
- **Page head** (`.page-head`): stacks vertically below ~600px; its controls (sprint select, buttons) go full width.
- **Tables** (Admin): wrap in an `overflow-x: auto` container so wide tables scroll instead of overflowing the viewport.
- **Modal**: already `max-width: 92vw`; reduce padding on small screens.
- Breakpoints: primary `768px`, secondary `480px` for finer tuning.

## Data Flow

Theme and sidebar state live entirely on the client (composables + `localStorage`). No backend changes.

## Error Handling / Edge Cases

- `matchMedia` unavailable (very old browser): fall back to `light`.
- `localStorage` blocked/throws: wrap reads/writes in try/catch; fall back to in-memory state for the session.
- Route change while drawer open on mobile: close the drawer (watch `route`).
- Resizing across the 768px boundary while the drawer is open: ensure no stuck overlay (reset/normalize `sidebarOpen` semantics per the active breakpoint via CSS — overlay styles only apply under the media query, so the same `sidebarOpen=true` renders as a docked panel on desktop and an overlay on mobile).

## Testing

- **Manual + Playwright** (no backend logic involved):
  - Toggle dark mode → `<html data-theme>` flips, colors change, reload preserves choice.
  - Fresh profile (no `localStorage.theme`) follows the emulated OS `prefers-color-scheme`.
  - Resize to 375px → top bar + hamburger appear, sidebar hidden, opening shows overlay drawer + backdrop, tapping a nav link closes it, board scrolls horizontally with snap.
  - Desktop collapse → main expands; reload remembers collapsed state.
  - Contrast spot-check on key text/badges in both themes.

## Files Touched

- `frontend/src/composables/useTheme.js` (new)
- `frontend/src/components/ThemeToggle.vue` (new)
- `frontend/src/views/AppLayout.vue` (top bar, hamburger, drawer, `sidebarOpen`)
- `frontend/src/assets/main.css` (variable refactor, `[data-theme="dark"]`, media queries)
- `frontend/src/main.js` or `App.vue` (initialize theme on boot)

## Acceptance Criteria

- [ ] Theme toggle visible; switching updates the whole app and persists across reloads.
- [ ] First visit with no saved preference matches the OS light/dark setting.
- [ ] No hardcoded color leaves an unreadable element in dark mode (audit all views: Board, Dashboard, Admin, Login, modal).
- [ ] At ≤768px: hamburger present, sidebar is an overlay drawer with backdrop, closes on nav/backdrop, board scrolls horizontally.
- [ ] At >768px: hamburger collapses/expands the docked sidebar and the state survives reload.
- [ ] Admin tables and the task modal remain usable (no horizontal overflow of the page) on a 375px viewport.
