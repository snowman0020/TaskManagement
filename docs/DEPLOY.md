# Deploy — Vercel (frontend) + Render (backend) + MongoDB Atlas (database)

Three managed services, all with a free tier. Deploy order matters:
**Atlas → Render → Vercel → (update Render CORS)**.

| Part | Where | Notes |
|------|-------|-------|
| Database | **MongoDB Atlas** | free M0 cluster; GridFS images work |
| Backend  | **Render** | Docker web service from `backend/Dockerfile` (`render.yaml` blueprint) |
| Frontend | **Vercel** | static Vite build (`frontend/vercel.json`) |

The repo already contains everything needed: `render.yaml`, `frontend/vercel.json`,
a `$PORT`-aware backend `Dockerfile`, and `dnspython` (for Atlas `mongodb+srv://`).

---

## 1. MongoDB Atlas (database)

1. Create an account at https://www.mongodb.com/atlas → **Create** a free **M0** cluster.
2. **Database Access** → Add Database User (username + password). Save them.
3. **Network Access** → Add IP Address → **Allow access from anywhere** (`0.0.0.0/0`).
   (Render's outbound IPs aren't static on the free plan, so allow-all is simplest;
   tighten later if you upgrade.)
4. **Connect** → **Drivers** → copy the connection string. It looks like:
   ```
   mongodb+srv://<user>:<password>@cluster0.xxxxx.mongodb.net/?retryWrites=true&w=majority
   ```
   Put your real user/password in. This is your **`MONGO_URI`**. (The app uses DB name
   `taskmanagement` from `MONGO_DB` — no need to add it to the URI.)

---

## 2. Render (backend)

1. Push this repo to GitHub (done). Go to https://render.com → **New → Blueprint**.
2. Pick this repository. Render reads **`render.yaml`** and proposes the `taskflow-api`
   Docker web service. Click **Apply**.
3. Open the service → **Environment** and set the secrets marked `sync: false`:
   - `MONGO_URI` → the Atlas string from step 1.
   - `ADMIN_PASSWORD` → a strong password (this is the seeded admin login).
   - `CORS_ORIGINS` → leave a placeholder for now (e.g. `https://example.vercel.app`);
     you'll set the real Vercel URL in step 4.
   - `JWT_SECRET` is auto-generated; `ENVIRONMENT=production`, `MONGO_DB`,
     `ADMIN_USERNAME` come from `render.yaml`.
4. Deploy. When live, note the URL, e.g. `https://taskflow-api.onrender.com`.
5. Verify: open `https://taskflow-api.onrender.com/api/health` → `{"status":"ok"}` and
   `…/docs` for the API docs.

> No blueprint? Create manually: **New → Web Service → Docker**, root/Dockerfile path
> `backend/Dockerfile`, context `backend/`, health check `/api/health`, then add the same
> env vars. Render injects `$PORT` automatically — the Dockerfile already binds it.

> Free tier sleeps after inactivity; the first request can take ~50s to wake.

---

## 3. Vercel (frontend)

1. Go to https://vercel.com → **Add New → Project** → import this repo.
2. **Root Directory** → set to **`frontend`**. Vercel auto-detects Vite (build
   `npm run build`, output `dist`, SPA rewrite from `frontend/vercel.json`).
3. **Environment Variables** → add:
   - `VITE_API_BASE` = your Render backend origin, **no trailing slash**, e.g.
     `https://taskflow-api.onrender.com`
   (The frontend calls `${VITE_API_BASE}/api/...`; build-time variable, so set it before
   deploying.)
4. Deploy. Note the URL, e.g. `https://taskflow.vercel.app`.

---

## 4. Wire CORS (back to Render)

1. Render → `taskflow-api` → **Environment** → set
   `CORS_ORIGINS` = your Vercel URL (comma-separated if several), e.g.
   `https://taskflow.vercel.app`
2. Save → Render redeploys.

---

## 5. Verify

- Open the Vercel URL → log in with `admin` / your `ADMIN_PASSWORD`.
- Create a task, attach an image, switch boards — all data lives in Atlas (images in
  GridFS).
- If login/board calls fail with a CORS error in the browser console, re-check that
  `CORS_ORIGINS` exactly matches the Vercel origin (scheme + host, no trailing slash).

## Required environment variables (backend)

| Var | Example | Set where |
|-----|---------|-----------|
| `ENVIRONMENT` | `production` | render.yaml |
| `MONGO_URI` | `mongodb+srv://…` | Render (from Atlas) |
| `MONGO_DB` | `taskmanagement` | render.yaml |
| `JWT_SECRET` | (generated) | Render |
| `ADMIN_USERNAME` / `ADMIN_PASSWORD` | `admin` / `<strong>` | render.yaml / Render |
| `CORS_ORIGINS` | `https://taskflow.vercel.app` | Render (Vercel URL) |

…and one for the **frontend**: `VITE_API_BASE` = the Render backend origin (Vercel).

> In production the backend refuses to start with the default `JWT_SECRET` or
> `ADMIN_PASSWORD`, so both must be real values.

## Custom domains (optional)
- Vercel: add your domain to the project; update `CORS_ORIGINS` on Render to include it.
- Render: add a custom domain; update `VITE_API_BASE` on Vercel and redeploy.

## Auto-deploy
Both Render (`autoDeploy: true`) and Vercel redeploy on every push to the connected
branch (the repo default is `develop`). Use a production branch (`main`) or Render/Vercel
branch settings if you want manual promotion.
