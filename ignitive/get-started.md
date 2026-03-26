# Get Started — Dev Smoke Test

Runs the full stack locally on the droplet: postgres + redis in Docker, server and backend as native processes.

## Prerequisites

- Docker + Docker Compose
- Python 3.11 (backend) and 3.12 (server) via `uv`
- Node.js 18–22 + npm

---

## Step 1 — Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d
```

Wait until both containers are healthy:

```bash
docker compose -f docker-compose.dev.yml ps
```

---

## Step 2 — Configure the server

```bash
cp server/.env.example server/.env
```

The defaults in `.env.example` already point to `localhost:5432` and `localhost:6379` — no edits needed for a local dev run. The one value you must set is a real LLM API key in the frontend later (Step 5).

Run database migrations:

```bash
cd server
uv run alembic upgrade head
cd ..
```

---

## Step 3 — Start the server

```bash
cd server
uv run uvicorn main:app --port 8001 --reload
```

Verify it's up: `curl http://localhost:8001/health` should return `{"status":"ok"}` or similar.

---

## Step 4 — Configure and start the backend

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set:
```
CORS_ORIGINS=http://localhost:5173
SERVER_URL=http://localhost:8001
```

Start the backend:

```bash
cd backend
uv run uvicorn main:api --port 8000 --reload
```

Verify: `curl http://localhost:8000/health`

---

## Step 5 — Start the frontend

```bash
npm install
```

Edit `.env.development` and confirm (or add) these values:
```
VITE_PROXY_URL=http://localhost:8001
VITE_USE_LOCAL_PROXY=false
```

This tells the frontend to use the server's auth and proxy chat requests through it.

```bash
npm run dev
```

Frontend will be at `http://localhost:5173`.

---

## Smoke Test Checklist

Open `http://localhost:5173` in your browser and run through these:

- [ ] **Register** — create a new account via the sign-up screen
- [ ] **Login** — log in with that account
- [ ] **Model config** — go to Settings, add an LLM API key (e.g. OpenAI)
- [ ] **Send a message** — type a simple prompt (e.g. "What is 2 + 2?")
- [ ] **SSE streaming** — confirm the response streams in (token by token, not all at once)
- [ ] **Agent activity** — confirm you see agent steps appearing (decompose, activate_agent, etc.)

If all five pass, Phase 1 is working end-to-end.

---

## Stopping everything

```bash
# Stop infrastructure
docker compose -f docker-compose.dev.yml down

# Kill server/backend with Ctrl+C in their terminals
```
