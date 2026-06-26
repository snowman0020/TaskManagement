# TaskFlow — Task Management System

A full-stack Kanban-style task management system with sprints, roles, drag-and-drop,
and a lead-time dashboard.

| Layer    | Tech                                        |
|----------|---------------------------------------------|
| Database | **MongoDB** 7                               |
| Backend  | **Python** · FastAPI · Motor (async) · JWT  |
| Frontend | **Vue 3** · Vite · Pinia · Vue Router · vuedraggable |

## Features

1. **MongoDB** persistence (async via Motor) with auto-created indexes.
2. **Vue 3** SPA frontend (Vite + Pinia + Vue Router).
3. **Python / FastAPI** REST backend.
4. **Login system** — JWT auth, login by username *or* email.
5. **Running task numbers** — atomic counter produces `TASK-1`, `TASK-2`, …
6. **Drag & drop** — Kanban board powered by `vuedraggable`, persisted server-side.
7. **Roles** — `admin`, `manager`, `member`, `viewer` with route + API guards.
8. **Git branches** — `dev`, `staging`, `release` (see below).
9. **`.gitignore`** — Python, Node, Docker, editor artifacts.
10. **Admin page** — manage users/roles, status columns, and sprints.
11. **Dashboard** — task overview, completion rate, and **lead time / cycle time**.
12. **Configurable status columns** — defaults `TODO`, `InProgress`, `QA`, `Done`; add/edit/remove with WIP limits.
13. **Sprint config** — auto-generate **2-week sprints on workdays (Mon–Fri)**.

## Project layout

```
TaskManagement/
├── backend/                 # FastAPI + Motor
│   ├── app/
│   │   ├── main.py          # app factory, lifespan, router wiring
│   │   ├── config.py        # env-driven settings
│   │   ├── database.py      # Mongo connection, indexes, running-number counter
│   │   ├── core/            # security (JWT/bcrypt), auth dependencies
│   │   ├── models/          # enums (Role)
│   │   ├── schemas/         # Pydantic request/response models
│   │   ├── routers/         # auth, users, tasks, sprints, status_columns, dashboard
│   │   └── services/        # sprint generation, seed defaults
│   ├── tests/               # in-process smoke + HTTP integration tests (mongomock)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Vue 3 SPA
│   ├── src/
│   │   ├── views/           # Login, Board, Dashboard, Admin, AppLayout
│   │   ├── components/      # TaskModal
│   │   ├── stores/          # Pinia auth store
│   │   ├── router/          # routes + auth/role guards
│   │   └── api/             # axios client w/ JWT interceptor
│   └── Dockerfile
├── docker-compose.yml       # mongo + backend + frontend
└── .gitignore
```

## Quick start (Docker)

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API + docs: http://localhost:8000/docs
- Default admin: **admin / admin1234** (change in production!)

## Local development

### Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env          # edit MONGO_URI, JWT_SECRET, admin creds
uvicorn app.main:app --reload # http://localhost:8000
```

On first boot the backend seeds the default admin account and the four status
columns (`TODO`, `InProgress`, `QA`, `Done`).

### Frontend

```bash
cd frontend
npm install
npm run dev                   # http://localhost:5173 (proxies /api to :8000)
```

### Tests

The tests run fully in-process against an in-memory Mongo (no server needed):

```bash
cd backend
pip install -r requirements-dev.txt
python tests/smoke_test.py    # seed, running numbers, sprint generation
python tests/http_test.py     # login, RBAC, create/move task, dashboard, leadtime
```

## Roles & permissions

| Action                          | admin | manager | member | viewer |
|---------------------------------|:-----:|:-------:|:------:|:------:|
| View board / dashboard          |   ✓   |    ✓    |   ✓    |   ✓    |
| Create / move / edit tasks      |   ✓   |    ✓    |   ✓    |        |
| Manage sprints & status columns |   ✓   |    ✓    |        |        |
| Manage users & roles            |   ✓   |         |        |        |

## How key features work

- **Running task numbers** — `database.next_sequence("task")` does an atomic
  `find_one_and_update($inc)` on a `counters` document, so numbers never collide.
- **Drag & drop** — the board uses a shared `vuedraggable` group; on drop the
  affected column is re-indexed and saved via `PATCH /api/tasks/reorder/bulk`.
- **Lead time** — moving a task out of the first column stamps `started_at`;
  moving it into the *done* column stamps `done_at`. The dashboard reports
  lead time (created→done) and cycle time (started→done).
- **Sprints** — `POST /api/sprints/generate` builds consecutive sprints that
  start on a Monday and end on the Friday of their final week (10 working days
  for a 2-week sprint). A non-Monday start date snaps forward to the next Monday.

## Git branches

```
main      → production-ready, tagged releases
release   → release candidates / hardening
staging   → pre-prod QA / UAT
dev       → integration branch for day-to-day work
```

Feature branches branch off `dev` and merge back via PR.

## Environment variables (backend)

| Var | Default | Notes |
|-----|---------|-------|
| `MONGO_URI` | `mongodb://localhost:27017` | |
| `MONGO_DB` | `taskmanagement` | |
| `JWT_SECRET` | `change-me-…` | **set a strong secret in prod** |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | |
| `ADMIN_USERNAME` / `ADMIN_EMAIL` / `ADMIN_PASSWORD` | `admin` / … / `admin1234` | seeded once |
| `CORS_ORIGINS` | `http://localhost:5173,…` | comma-separated |
