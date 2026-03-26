# General Backend Reverse Proxy

## Context

In cloud mode, the frontend's `fetchPost`/`fetchGet` functions (used for model validation, task control, tool management, chat, etc.) need to reach the backend. Currently only the SSE chat proxy (`/chat/proxy/{project_id}/{task_id}`) forwards to the backend. All other backend endpoints return `ERR_CONNECTION_REFUSED` because the frontend tries `localhost:5001` (local backend that doesn't exist in cloud mode).

## Approach

Add a general reverse proxy middleware on the server that catches all requests to `/api/v1/chat/*`, `/api/v1/task/*`, `/api/v1/model/*`, `/api/v1/install/*`, `/api/v1/tools/*`, `/api/v1/oauth/*`, `/api/v1/browser/*`, `/api/v1/linkedin/*` and forwards them to the backend. This mirrors what the existing chat proxy does but for all endpoints, not just SSE.

The proxy will:
1. Require JWT auth (same as chat proxy)
2. Strip `/api/v1` prefix before forwarding (backend has no prefix)
3. Inject `X-User-Id` and `X-User-Email` headers
4. Forward all HTTP methods, query params, headers, and request body
5. Handle SSE streaming transparently (for `/chat/*` endpoints)
6. Return 503 if backend is down

## Changes

### 1. `server/app/middleware/backend_proxy.py` — New reverse proxy middleware

A FastAPI middleware (ASGI) that intercepts requests matching backend paths and proxies them. Uses `httpx.AsyncClient` for async HTTP forwarding with streaming support.

Key behaviors:
- Path matching: routes starting with `/chat/`, `/task/`, `/model/`, `/install/`, `/tools/`, `/oauth/`, `/browser/`, `/linkedin/`
- Auth: extracts JWT from `Authorization` header, validates it, gets user info
- SSE passthrough: detects `text/event-stream` response and streams chunks back
- Error handling: returns 503 with JSON error body if backend unreachable
- Backend URL: from `BACKEND_URL` env var (same as chat proxy)

### 2. `server/main.py` — Register the proxy middleware

Add the backend proxy middleware after route registration but before other middleware. The proxy must run early enough to catch requests before the 404 handler.

## Files to modify

| File | Change |
|------|--------|
| `server/app/middleware/backend_proxy.py` | New: general reverse proxy middleware |
| `server/main.py` | Register proxy middleware |

## Verification

1. Restart server
2. In Electron app, go to Settings → Models
3. Add an LLM API key (e.g. OpenAI) and click Validate — should succeed instead of `ERR_CONNECTION_REFUSED`
4. Chat functionality should also work through the proxy
