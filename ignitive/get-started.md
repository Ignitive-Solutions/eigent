# Get Started — Dev Smoke Test

Split across two machines: a **server machine** (droplet, Ubuntu) and a **client machine** (your PC, Windows).

---

## Server Machine (Droplet / Ubuntu)

Runs PostgreSQL, Redis, the auth server, and the orchestration backend.

### Prerequisites

- Docker + Docker Compose
- Python 3.12 (server) and 3.11 (backend) via `uv`
- tmux (`sudo apt install tmux`)

### Step 1 — Start infrastructure

```bash
docker compose -f docker-compose.dev.yml up -d
```

Wait until both containers are healthy:

```bash
docker compose -f docker-compose.dev.yml ps
```

If the containers keep restarting, or you see "database eigent does not exist" later, reset the volumes:

```bash
docker compose -f docker-compose.dev.yml down -v
docker compose -f docker-compose.dev.yml up -d
```

### Step 2 — Configure the server

```bash
cp server/.env.example server/.env
```

Edit `server/.env`:
```
BACKEND_URL=http://localhost:8002
GOOGLE_LOGIN_CLIENT_ID=<your-google-client-id>
GOOGLE_LOGIN_CLIENT_SECRET=<your-google-client-secret>
```

Run database migrations:

```bash
cd server
uv run alembic upgrade head
cd ..
```

### Step 3 — Start server + backend in tmux

Using tmux keeps them running even if your SSH session drops.

```bash
tmux new -s ignitive

cd server
nohup uv run uvicorn main:api --port 8001 --reload > /tmp/server.log 2>&1 &
cd ../backend
nohup uv run uvicorn main:api --port 8002 --reload > /tmp/backend.log 2>&1 &
```

Detach from tmux: press **Ctrl+B**, then **D**.

Verify:
```bash
curl http://localhost:8001/health   # should return {"status":"ok"}
curl http://localhost:8002/health
```

To reattach later: `tmux attach -t ignitive`
To check logs: `tail -f /tmp/server.log` or `tail -f /tmp/backend.log`

---

## Client Machine (Your PC / Windows)

Runs the Electron app. No Python, no Docker needed.

### Prerequisites

- Node.js 18–22 (includes npm) — download from https://nodejs.org
- VS Code with the **Remote - SSH** extension

All commands below use **PowerShell**.

### Step 4 — Get the source

```powershell
git clone <your-repo-url>
cd eigent
```

### Step 5 — Install dependencies

```powershell
npm install
```

### Step 6 — Configure the frontend

Open `.env.development` in VS Code:

```
VITE_PROXY_URL=https://eigent-dev.ignitive.ai
VITE_USE_LOCAL_PROXY=false
```

### Step 7 — Port forwarding via VS Code

1. In VS Code, open the **Remote - SSH** panel and connect to your droplet
2. Open the **Ports** tab (bottom panel)
3. Click **"Forward a Port"** and enter `8001`
4. Repeat for port `8002`

This makes `localhost:8001` and `localhost:8002` on your PC route to the droplet.

### Step 8 — Start the Electron app

```powershell
$env:VSCODE_DEBUG="true"; npm run dev
```

Open **`http://localhost:7777`** in your browser — the login screen should appear.

---

## Smoke Test Checklist

Open `http://localhost:7777` on your client machine and run through these:

- [ ] **Login** — click "Log in", complete Google OAuth, app should show the main UI
- [ ] **Model config** — go to Settings, add an LLM API key (e.g. OpenAI)
- [ ] **Send a message** — type a simple prompt (e.g. "What is 2 + 2?")
- [ ] **SSE streaming** — confirm the response streams in (token by token, not all at once)
- [ ] **Agent activity** — confirm you see agent steps appearing (decompose, activate_agent, etc.)

If all pass, Phase 1 is working end-to-end.

---

## Stopping everything

**Server machine (droplet):**
```bash
tmux attach -t ignitive
# Kill both processes:
kill $(lsof -t -i:8001) $(lsof -t -i:8002)
docker compose -f docker-compose.dev.yml down
```

**Client machine (Windows):**
```powershell
# Kill npm dev server with Ctrl+C in the terminal
```
