"""General reverse proxy — forwards backend API requests to the backend service.

In cloud mode, the frontend talks to the server for auth but needs to reach
the backend for orchestration (model validation, chat, task control, tools).
This middleware intercepts backend-bound paths, authenticates via JWT, injects
user-context headers, and proxies to the backend (default http://backend:8002).
"""

import logging

import httpx
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.environment import env
from app.model.user.user import User
from app.shared.auth.user_auth import V1UserAuth
from app.shared.auth.token_blacklist import is_blacklisted

logger = logging.getLogger("backend_proxy")

_BACKEND_URL = env("BACKEND_URL", "http://localhost:8002").rstrip("/")

# Backend routes to proxy (matched after stripping /api/v1 prefix)
_BACKEND_PREFIXES = (
    "/chat",
    "/task",
    "/model",
    "/install",
    "/tools",
    "/oauth",
    "/browser",
    "/linkedin",
)

# HTTP methods that carry a body
_METHODS_WITH_BODY = {"POST", "PUT", "PATCH"}

# Headers to never forward to the backend
_STRIP_HEADERS = {
    "host",
    "content-length",
    "transfer-encoding",
    "connection",
}

# Headers to always inject into proxied requests
_INJECT_HEADERS = {
    "X-Forwarded-Host": "",
    "X-Forwarded-For": "",
    "X-Forwarded-Proto": "https",
}


class BackendProxyMiddleware(BaseHTTPMiddleware):
    """ASGI middleware that proxies backend API requests to the backend service."""

    async def dispatch(self, request: Request, call_next) -> Response:
        path = request.url.path

        # Only intercept requests under /api/v1 with a backend prefix
        if not path.startswith("/api/v1/"):
            return await call_next(request)

        inner = path[len("/api/v1/"):]
        if not any(inner.startswith(p) for p in _BACKEND_PREFIXES):
            return await call_next(request)

        # Skip the existing chat SSE proxy endpoint
        if inner.startswith("/chat/proxy/"):
            return await call_next(request)

        # 1. Authenticate
        auth_header = request.headers.get("authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response(
                content=b'{"detail":"Not authenticated"}',
                status_code=401,
                headers={"content-type": "application/json"},
            )

        token = auth_header[7:]
        try:
            auth = V1UserAuth.decode_token(token)
            if is_blacklisted(auth.id):
                return Response(
                    content=b'{"detail":"Token revoked"}',
                    status_code=401,
                    headers={"content-type": "application/json"},
                )
        except Exception:
            return Response(
                content=b'{"detail":"Invalid or expired token"}',
                status_code=401,
                headers={"content-type": "application/json"},
            )

        # 2. Resolve user email
        user_email = ""
        try:
            from app.core.database import session as get_session
            with next(get_session()) as db:
                user = db.get(User, auth.id)
                if user:
                    user_email = user.email or ""
        except Exception:
            pass

        # 3. Build backend URL
        backend_url = f"{_BACKEND_URL}{inner}"
        if request.url.query:
            backend_url += f"?{request.url.query}"

        # 4. Build forwarding headers
        forward_headers = dict(request.headers)
        for h in _STRIP_HEADERS:
            forward_headers.pop(h, None)
        forward_headers.pop("authorization", None)
        forward_headers["X-User-Id"] = str(auth.id)
        forward_headers["X-User-Email"] = user_email
        forward_headers.update(_INJECT_HEADERS)

        # 5. Forward request
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                # Read body for methods that support it
                body = None
                if request.method in _METHODS_WITH_BODY:
                    body = await request.body()

                req = client.build_request(
                    method=request.method,
                    url=backend_url,
                    headers=forward_headers,
                    content=body,
                )
                response = await client.send(req)

                # 6. Stream response back
                is_streaming = (
                    response.headers.get("content-type", "").startswith("text/event-stream")
                    or response.headers.get("transfer-encoding", "").lower() == "chunked"
                )

                if is_streaming:
                    return Response(
                        content=response.aiter_bytes(),
                        status_code=response.status_code,
                        headers={
                            k: v
                            for k, v in response.headers.items()
                            if k.lower() != "transfer-encoding"
                        },
                    )
                else:
                    return Response(
                        content=response.content,
                        status_code=response.status_code,
                        headers=dict(response.headers),
                    )
        except httpx.ConnectError:
            logger.error("Backend proxy: connection refused to %s", _BACKEND_URL)
            return Response(
                content=b'{"detail":"Backend service unavailable"}',
                status_code=503,
                headers={"content-type": "application/json"},
            )
        except httpx.TimeoutException:
            logger.error("Backend proxy: timeout connecting to %s", _BACKEND_URL)
            return Response(
                content=b'{"detail":"Backend service timeout"}',
                status_code=504,
                headers={"content-type": "application/json"},
            )
        except Exception as e:
            logger.error("Backend proxy error: %s", e)
            return Response(
                content=b'{"detail":"Backend proxy error"}',
                status_code=502,
                headers={"content-type": "application/json"},
            )
