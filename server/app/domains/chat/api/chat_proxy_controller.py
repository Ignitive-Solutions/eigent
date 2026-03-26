# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

"""Chat SSE proxy endpoint.

Forwards authenticated POST requests to the backend's /chat endpoint and
streams the SSE response transparently back to the client.  The backend
container is auth-free (internal only); this endpoint enforces authentication
on the server side and injects user-context headers before proxying.
"""

import logging
from typing import AsyncIterator

import httpx
from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from app.core.environment import env
from app.shared.auth.user_auth import V1UserAuth, auth_must

logger = logging.getLogger("chat_proxy_controller")

router = APIRouter(prefix="/chat", tags=["Chat Proxy"])

# Default backend URL — override via BACKEND_URL env var
_DEFAULT_BACKEND_URL = "http://backend:8000"


def _backend_url() -> str:
    return env("BACKEND_URL", _DEFAULT_BACKEND_URL).rstrip("/")


async def _stream_backend(
    backend_chat_url: str,
    body: bytes,
    extra_headers: dict,
) -> AsyncIterator[bytes]:
    """Open a streaming connection to the backend and yield raw chunks."""
    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream(
            "POST",
            backend_chat_url,
            content=body,
            headers=extra_headers,
        ) as response:
            response.raise_for_status()
            async for chunk in response.aiter_bytes():
                if chunk:
                    yield chunk


@router.post("/proxy/{project_id}/{task_id}", name="proxy chat SSE to backend")
async def proxy_chat(
    project_id: str,
    task_id: str,
    request: Request,
    auth: V1UserAuth = Depends(auth_must),
):
    """Proxy a chat request to the backend container, streaming the SSE response.

    - Requires a valid JWT (enforced via ``auth_must``).
    - Forwards the raw request body to ``{BACKEND_URL}/chat``.
    - Injects ``X-User-Id`` and ``X-User-Email`` headers so the backend can
      identify the caller without performing its own auth.
    - Returns the backend's ``text/event-stream`` response as-is.
    """
    body = await request.body()

    user = auth.user
    forward_headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "X-User-Id": str(user.id),
        "X-User-Email": str(user.email),
    }

    backend_chat_url = f"{_backend_url()}/chat"

    logger.info(
        "Proxying chat request to backend",
        extra={
            "project_id": project_id,
            "task_id": task_id,
            "user_id": user.id,
            "backend_url": backend_chat_url,
        },
    )

    return StreamingResponse(
        _stream_backend(backend_chat_url, body, forward_headers),
        media_type="text/event-stream",
    )
