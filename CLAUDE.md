# Ignitive SaaS — Eigent Fork

## Project
Proprietary multi-tenant AI orchestration platform for construction, built on the Eigent fork.
Plan: `.claude/plans/planned-1-ignitive-saas-architecture.md`

## Architecture
- `server/` — FastAPI: auth (JWT), PostgreSQL, Redis, Celery, trigger system. Runs on port 8001.
- `backend/` — FastAPI: CAMEL orchestration engine (agents, SSE, tools). Internal only, port 8000.
- `src/` + `electron/` — React/Electron frontend. Proxy mode points to cloud via `VITE_PROXY_URL`.
- Production domain: `eigent-dev.ignitive.ai`

## Dev Commands
- Frontend: `bun install && bun run dev`
- Backend: `cd backend && uv run uvicorn main:api --reload`
- Server: `cd server && uv run uvicorn main:app --port 8001 --reload`
- Production stack: `docker compose -f docker-compose.prod.yml up -d`

## Key Files
- `docker-compose.prod.yml` — production 7-container stack (server, backend, postgres, redis, celery x2, caddy)
- `Caddyfile` — reverse proxy config for eigent-dev.ignitive.ai
- `.env.production` — frontend build config for cloud proxy mode
- `BUILD.md` — how to build the Electron app for cloud proxy mode
- `server/app/domains/chat/api/chat_proxy_controller.py` — SSE proxy from server → backend

## Conventions
- Conventional Commits (`feat:`, `fix:`, `chore:` etc.)
- uv for Python, bun for JS
- Secrets in `.env` files (gitignored). `.env.production` is NOT a secret — it's committed.
- Backend CORS restricted to `server:8001` + localhost only (never public)
