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

### Step 3 — Start server + backend 

```bash
# Launch backend server
cd server
uv run uvicorn main:api --port 8001 --reload
# Create a new terminal, launch database server
cd backend
uv run uvicorn main:api --port 8002 --reload


Verify:
```bash
curl http://localhost:8001/health   # should return {"status":"ok"}
curl http://localhost:8002/health
```

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
3. Click **"Forward a Port"** and enter `8002`

This makes `localhost:8002` on your PC route to the droplet. The server is connected thru the subdomain.

### Step 8 — Start the Electron app

```powershell
npm run dev
```

Open **`http://localhost:5173`** in your browser — the login screen should appear.

---

## Stopping everything

**Server machine (droplet):**
```bash
# kill the 2 terminals running back end + db with Ctrl+C
docker compose -f docker-compose.dev.yml down
```

**Client machine (Windows):**
```powershell
# Kill npm dev server with Ctrl+C in the terminal
```
