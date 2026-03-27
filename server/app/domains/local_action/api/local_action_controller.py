# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

"""Local action dispatch endpoint.

Receives tool requests from the cloud backend (via HTTP POST), publishes
them to the user's Electron client via Redis pub/sub, and waits for the
client to execute the action and return the result.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.core.redis_utils import get_redis_manager
from app.shared.auth.user_auth import V1UserAuth, auth_must

logger = logging.getLogger("local_action_controller")

router = APIRouter(prefix="/local-action", tags=["Local Action"])

ALLOWED_ACTIONS = {"list_files", "read_file", "file_exists"}


class LocalActionRequest(BaseModel):
    request_id: str
    action: str
    params: dict = {}
    api_task_id: str = ""


class LocalActionResponse(BaseModel):
    request_id: str
    success: bool
    result: object = None
    error: str | None = None


@router.post("", name="dispatch local action")
async def dispatch_local_action(
    body: LocalActionRequest,
    auth: V1UserAuth = Depends(auth_must),
):
    """Dispatch a local action to the user's connected Electron client.

    The flow:
    1. Publish tool_request to Redis pub/sub (routed to the user's
       WebSocket session by the existing subscriber loop).
    2. Poll Redis for the client's tool_response.
    3. Return the result to the backend.
    """
    user_id = str(auth.id)
    redis = get_redis_manager()

    # Validate action against whitelist
    if body.action not in ALLOWED_ACTIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Action '{body.action}' is not allowed",
        )

    # Check user has an active WebSocket session
    if not redis.has_active_sessions_for_user(user_id):
        raise HTTPException(
            status_code=503,
            detail="No active local client connected. Is the Electron app running?",
        )

    # Publish to the pub/sub channel — the existing subscriber loop
    # in trigger_execution_controller.py will forward this to the user's
    # WebSocket connection.
    published = redis.publish_tool_request(
        request_id=body.request_id,
        user_id=user_id,
        action=body.action,
        params=body.params,
    )

    if not published:
        raise HTTPException(
            status_code=503,
            detail="Failed to dispatch action to local client",
        )

    logger.info(
        "Local action dispatched, waiting for response",
        extra={
            "request_id": body.request_id,
            "action": body.action,
            "user_id": user_id,
        },
    )

    # Wait for the Electron client's response
    response = await redis.wait_for_tool_response(
        body.request_id, timeout=30.0
    )

    if response is None:
        logger.warning(
            "Local action timed out",
            extra={"request_id": body.request_id, "action": body.action},
        )
        return LocalActionResponse(
            request_id=body.request_id,
            success=False,
            error="Timeout: local client did not respond within 30 seconds",
        )

    logger.info(
        "Local action completed",
        extra={
            "request_id": body.request_id,
            "action": body.action,
            "success": response.get("success"),
        },
    )

    return LocalActionResponse(
        request_id=body.request_id,
        success=response.get("success", False),
        result=response.get("result"),
        error=response.get("error"),
    )
