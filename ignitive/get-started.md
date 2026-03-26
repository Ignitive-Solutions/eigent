# Get Started — Dev Smoke Test

Split across two machines: a **server machine** (droplet, Ubuntu) and a **client machine** (your PC, Windows).

---

## Server Machine (Droplet / Ubuntu)

Runs PostgreSQL, Redis, the auth server, and the orchestration backend.

### Prerequisites

- Docker + Docker Compose
- Python 3.12 (server) and 3.11 (backend) via `uv`

### Step 1 — Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d
```

Wait until both containers are healthy:

```bash
docker compose -f docker-compose.dev.yml ps
```

### Step 2 — Configure the server

```bash
cp server/.env.example server/.env
```

Defaults already point to `localhost:5432` and `localhost:6379`. No edits needed for local dev.

The `BACKEND_URL` in `.env.example` defaults to `http://backend:8002` (Docker service name). For local dev with native processes, change it to:

```
BACKEND_URL=http://localhost:8002
```

Run database migrations:

```bash
cd server
uv run alembic upgrade head
cd ..
```

### Step 3 — Start the server

```bash
cd server
uv run uvicorn main:api --port 8001 --reload
```

Verify: `curl http://localhost:8001/health` should return `{"status":"ok"}`.

### Step 4 — Configure and start the backend

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
uv run uvicorn main:api --port 8002 --reload
```

Verify: `curl http://localhost:8002/health`

No firewall changes needed — the SSH tunnel handles connectivity securely.

---

## Client Machine (Your PC / Windows)

Runs only the React frontend dev server. No Python, no Docker needed.

### Prerequisites

- Node.js 18–22 (includes npm) — download from https://nodejs.org
- Git for Windows — download from https://git-scm.com
- SSH client (included with Git for Windows, or use Windows OpenSSH)

All commands below use **PowerShell**.

### Step 6 — Get the source

```powershell
git clone <your-repo-url>
cd eigent
```

### Step 7 — Install dependencies

```powershell
npm install
```

### Step 8 — Configure the frontend

Open `.env.development` in Notepad or VS Code:

```
VITE_PROXY_URL=http://localhost:8001
VITE_USE_LOCAL_PROXY=false
```

This points the frontend at `localhost:8001`, which the SSH tunnel (Step 9) will route to the droplet.

### Step 9 — Create the SSH tunnel

Open a **second** PowerShell window and leave it running:

```powershell
ssh -L 8001:localhost:8001 your-user@<your-droplet-ip> -N
```

- `-L 8001:localhost:8001` — forwards your PC's port 8001 to the droplet's port 8001
- `-N` — no remote shell, just the tunnel
- Keep this window open while testing

### Step 10 — Start the frontend

```powershell
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## Smoke Test Checklist

Open `http://localhost:5173` on your client machine and run through these:

- [ ] **Register** — create a new account via the sign-up screen
- [ ] **Login** — log in with that account
- [ ] **Model config** — go to Settings, add an LLM API key (e.g. OpenAI)
- [ ] **Send a message** — type a simple prompt (e.g. "What is 2 + 2?")
- [ ] **SSE streaming** — confirm the response streams in (token by token, not all at once)
- [ ] **Agent activity** — confirm you see agent steps appearing (decompose, activate_agent, etc.)

If all six pass, Phase 1 is working end-to-end.

---

## Stopping everything

**Server machine (droplet):**
```bash
docker compose -f docker-compose.dev.yml down
# Kill server/backend with Ctrl+C
```

**Client machine (Windows):**
```powershell
# Kill npm dev server with Ctrl+C in the terminal
```
