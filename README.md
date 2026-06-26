# TaskFlow — Task Management System / ระบบจัดการงาน

A full-stack, multi-board Kanban task management system with sprints, roles, drag-and-drop,
image attachments, comments, notifications, a lead-time dashboard, dark mode, and a
responsive UI.

ระบบจัดการงานแบบ Kanban full-stack รองรับหลาย board, sprint, สิทธิ์ผู้ใช้, ลาก-วาง,
แนบรูป, คอมเมนต์, แจ้งเตือน, dashboard lead-time, dark mode และ responsive

| Layer    | Tech                                                 |
|----------|------------------------------------------------------|
| Database | **MongoDB** 7 (+ GridFS for images)                  |
| Backend  | **Python** · FastAPI · Motor (async) · JWT           |
| Frontend | **Vue 3** · Vite · Pinia · Vue Router · vuedraggable |

## Features / ฟังก์ชันทั้งหมด

### Board & Tasks / บอร์ดและงาน
- **Kanban board, drag & drop** — drag cards between configurable status columns; order persisted server-side. / ลาก-วางการ์ดข้าม column, บันทึกลำดับที่ server
- **Board views** — toggle **Active Sprint / Backlog / All**, plus a "jump to sprint" dropdown. / สลับมุมมอง Active Sprint / Backlog / All + เลือก sprint เจาะจง
- **Assignee filter** — filter the board by user (All · Me · each user · Unassigned). / กรองงานตามผู้รับผิดชอบ
- **Task fields** — title, description, status, priority, assignee, sprint, story points, **expected date**. / ฟิลด์งาน: หัวข้อ, รายละเอียด, สถานะ, priority, ผู้รับผิดชอบ, sprint, story points, วันที่คาดว่าเสร็จ
- **Image attachments** — attach **multiple images per task** (GridFS), thumbnails + remove, `📎` count badge. / แนบรูปได้หลายรูปต่องาน (GridFS) + ลบ + badge จำนวน
- **Comments & replies** — comment on a task and reply (one level); delete own (admin/manager any). / คอมเมนต์ + reply 1 ชั้น, ลบของตัวเอง (admin/manager ลบได้ทุกอัน)
- **Move history** — per-task audit log of status changes (who / from → to / when). / ประวัติการย้ายงาน (ใคร/จาก→ถึง/เมื่อ)
- **Running task numbers** — atomic per-board counter, e.g. `TASK-1`, or a board's own `MOB-500`. / เลขรันงานอัตโนมัติ ต่อ board

### Multi-board (Channels) / หลายบอร์ด
- **Multiple boards** — each board has its own tasks, sprints, and status columns. / แต่ละ board มี task/sprint/column ของตัวเอง
- **Per-board running number** — configurable **prefix + start number** per board. / กำหนด prefix + เลขเริ่มต้น ต่อ board
- **Membership** — admin assigns users to boards; non-members are denied access. / admin กำหนด member เข้า board; ไม่ใช่ member เข้าไม่ได้
- **Board switcher** — top-bar dropdown; the selection scopes the whole UI and is remembered. / dropdown สลับ board บน top bar, จำค่าไว้

### Sprints / สปรินต์
- **Auto-generate sprints** — consecutive **2-week Mon–Fri** sprints (snaps to Monday). / สร้าง sprint อัตโนมัติ 2 สัปดาห์ จ.–ศ.
- **Per-sprint manday** — set planned capacity (man-days) per sprint. / กำหนด manday (กำลังคน) ต่อ sprint
- **Complete sprint** — mark completed and **delete that sprint's done tasks** (confirmed). / ปิด sprint แล้วลบงานที่ done ของ sprint นั้น (มี confirm)

### Notifications / การแจ้งเตือน
- **In-app notifications** — on task **move**, **assign**, and **sprint complete**; the actor is never notified of their own action. / แจ้งเตือนเมื่อย้ายงาน / ถูก assign / ปิด sprint (ไม่แจ้งคนทำเอง)
- **Bell with unread badge** — dropdown list, **30s polling**, mark-all-read on open, **clear all**. / 🔔 badge นับ unread, poll ทุก 30 วิ, อ่านหมดเมื่อเปิด, ลบทั้งหมดได้

### UI / หน้าตา
- **Dark mode** — light/dark toggle, persisted, defaults to OS preference. / สลับ light/dark, จำค่า, ค่าเริ่มต้นตาม OS
- **Responsive** — phone-friendly; sidebar collapses to a hamburger drawer. / รองรับมือถือ; sidebar ยุบเป็น hamburger
- **Date picker** — native calendar on all date inputs. / date picker ทุกช่องวันที่
- **Timestamps in UTC+7** — times shown in Asia/Bangkok. / เวลาแสดงเป็น UTC+7 (Asia/Bangkok)

### Admin & Access / แอดมินและสิทธิ์
- **Login** — JWT auth, login by username *or* email. / login ด้วย JWT, ใช้ username หรือ email
- **Roles** — `admin` / `manager` / `member` / `viewer` with route + API guards. / สิทธิ์ 4 ระดับ คุมทั้ง route และ API
- **Admin page** — manage users/roles, status columns (drag-reorder, **editable key** with cascade, WIP limits), sprints, and boards. / จัดการ user, status column (ลากจัดลำดับ + แก้ key + WIP), sprint, board
- **Dashboard** — totals, completion rate, **lead time / cycle time**, tasks by status/assignee — scoped to the active board. / สรุปงาน, completion rate, lead/cycle time, แยกตาม board

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
│   │   ├── routers/         # auth, users, boards, tasks, task_images, comments,
│   │   │                    #   notifications, sprints, status_columns, dashboard
│   │   └── services/        # seed/migration, sprint generation, board access,
│   │                        #   notifications, image validation
│   ├── tests/               # smoke + http (mongomock) + images (real Mongo/GridFS)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/                # Vue 3 SPA
│   ├── src/
│   │   ├── views/           # Login, Board, Dashboard, Admin, AppLayout
│   │   ├── components/      # TaskModal, ImageUploader, TaskComments, DateField,
│   │   │                    #   NotificationBell, BoardSwitcher, ThemeToggle
│   │   ├── composables/     # useTheme
│   │   ├── stores/          # Pinia: auth, board (active board)
│   │   ├── router/          # routes + auth/role guards
│   │   └── api/             # axios client w/ JWT interceptor
│   └── Dockerfile
├── docker-compose.yml       # mongo + backend + frontend
└── .gitignore
```

## Getting started

After cloning, you have three ways to run the app. **Default login: `admin` / `admin1234`.**

### Prerequisites

| | Needed for | Notes |
|---|---|---|
| **Docker** | the database (and the all-in-one option) | runs MongoDB; the helper script starts it for you |
| **Python 3.12** | backend | 3.10+ works; **avoid 3.14** (`pydantic-core` build error). `py -3.12` on Windows |
| **Node 18+** | frontend | `npm` |

> No Docker? Run a MongoDB yourself on `localhost:27017`, or
> `docker run -d -p 27017:27017 --name tm-mongo mongo:7`.

### Option 1 — One command (recommended)

Starts MongoDB (via Docker) + backend (`:8000`) + frontend (`:5173`), each in its own window.
It auto-selects Python 3.12 and uses the venv directly (no execution-policy prompt).

```powershell
# Windows (PowerShell)
.\dev.ps1
```

```bash
# macOS / Linux
./dev.sh
```

Then open **http://localhost:5173**.

### Option 2 — Docker (zero local setup)

Runs the whole stack in containers:

```bash
docker compose up --build
```

- Frontend: http://localhost:8080
- Backend API + docs: http://localhost:8000/docs

### Option 3 — Manual (two terminals)

**Terminal 1 — backend** (`http://localhost:8000`, docs at `/docs`):

```bash
cd backend
python -m venv .venv
# Windows:        .\.venv\Scripts\Activate.ps1
# macOS / Linux:  source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # optional: edit MONGO_URI, JWT_SECRET, admin creds
uvicorn app.main:app --reload
```

**Terminal 2 — frontend** (`http://localhost:5173`, proxies `/api` → `:8000`):

```bash
cd frontend
npm install
npm run dev
```

Make sure MongoDB is running first (see Prerequisites). On first boot the backend
seeds the default admin and the four status columns (`TODO`, `InProgress`, `QA`, `Done`).

> The dev server picks the next free port if `5173` is taken (e.g. `5174`) — check the terminal output.

### Per-part helper scripts

| Goal | Windows (PowerShell) | macOS / Linux |
|------|----------------------|---------------|
| Everything (Mongo + backend + frontend) | `.\dev.ps1` | `./dev.sh` |
| Backend only: setup venv + install + run | `cd backend; .\dev.ps1` | `cd backend && ./dev.sh` |
| Backend: quick start (after setup) | `cd backend; .\start.ps1` | `cd backend && ./dev.sh` |
| Backend tests | `cd backend; .\test.ps1` | `cd backend && ./test.sh` |
| Frontend only | `cd frontend; .\dev.ps1` | `cd frontend && ./dev.sh` |

## Tests

`smoke_test.py` and `http_test.py` run fully in-process against an in-memory Mongo.
`images_test.py` exercises GridFS image upload and needs a **real** MongoDB running
(`tm-mongo` on `:27017`), because the in-memory mock has no GridFS.

```bash
cd backend
pip install -r requirements-dev.txt
python tests/smoke_test.py    # seed, running numbers, sprint generation
python tests/http_test.py     # login, RBAC, tasks, board filters, sprint manday, move history
python tests/images_test.py   # image upload/limits/RBAC (needs a running MongoDB)
```

## Roles & permissions

| Action                          | admin | manager | member | viewer |
|---------------------------------|:-----:|:-------:|:------:|:------:|
| View board / dashboard          |   ✓   |    ✓    |   ✓    |   ✓    |
| Create / move / edit tasks      |   ✓   |    ✓    |   ✓    |        |
| Manage sprints & status columns |   ✓   |    ✓    |        |        |
| Manage users & roles            |   ✓   |         |        |        |

## How key features work

- **Multi-board** — tasks/sprints/status columns carry a `board_id`; reads/creates
  are scoped to it (defaulting to a seeded **Default** board) and gated by board
  membership. On first boot, existing data is migrated into the Default board.
- **Running task numbers** — an atomic per-board counter (`counters` doc
  `task:<board_id>`, `find_one_and_update($inc)`), formatted `<board prefix>-<n>`,
  so numbers never collide and each board has its own series.
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
