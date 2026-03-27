# ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

"""Local action toolkit for cloud mode.

Dispatches file operations (list_files, read_file, etc.) to the user's
Electron app via the server's WebSocket/Redis bridge, then returns the
result to the CAMEL agent.
"""

import json
import logging
import uuid

import httpx
from camel.toolkits.function_tool import FunctionTool

from app.agent.toolkit.abstract_toolkit import AbstractToolkit
from app.component.environment import env
from app.service.task import Agents

logger = logging.getLogger("local_action_toolkit")

# URL of the server's local-action dispatch endpoint
_SERVER_ACTION_URL = env(
    "SERVER_ACTION_URL", "http://server:8001/api/v1/local-action"
)

# How long to wait for the Electron client to respond
_RESPONSE_TIMEOUT = 30.0

ALLOWED_ACTIONS = {"list_files", "read_file", "file_exists"}


class LocalActionToolkit(AbstractToolkit):
    """Toolkit that dispatches file operations to the local Electron client.

    The flow is:
    1. CAMEL agent calls a tool (e.g. list_files)
    2. This toolkit POSTs the request to the server's /local-action endpoint
    3. The server publishes to Redis pub/sub → WebSocket → Electron app
    4. Electron app executes via IPC and sends response back
    5. Server returns the response to this toolkit
    """

    agent_name: str = Agents.document_agent

    def __init__(self, api_task_id: str):
        self.api_task_id = api_task_id

    def _dispatch(self, action: str, params: dict) -> str:
        """Synchronous dispatch — POST to server, wait for response."""
        if action not in ALLOWED_ACTIONS:
            return f"Error: Action '{action}' is not allowed"

        request_id = str(uuid.uuid4())

        payload = {
            "request_id": request_id,
            "action": action,
            "params": params,
            "api_task_id": self.api_task_id,
        }

        logger.info("Dispatching local action", extra={
            "request_id": request_id,
            "action": action,
            "api_task_id": self.api_task_id,
        })

        try:
            with httpx.Client(timeout=_RESPONSE_TIMEOUT) as client:
                resp = client.post(
                    _SERVER_ACTION_URL,
                    json=payload,
                )
                resp.raise_for_status()
                data = resp.json()

            if data.get("success"):
                return json.dumps(data.get("result"), indent=2)
            else:
                error_msg = data.get("error", "Unknown error")
                logger.warning(
                    "Local action failed",
                    extra={"request_id": request_id, "error": error_msg},
                )
                return f"Error: {error_msg}"

        except httpx.TimeoutException:
            msg = f"Timeout waiting for local action '{action}' (request_id={request_id})"
            logger.warning(msg)
            return f"Error: {msg}"
        except httpx.HTTPStatusError as e:
            logger.error(
                "Server returned error for local action",
                extra={"status": e.response.status_code, "request_id": request_id},
            )
            return f"Error: Server returned HTTP {e.response.status_code}"
        except Exception as e:
            logger.error(
                "Failed to dispatch local action",
                extra={"request_id": request_id, "error": str(e)},
            )
            return f"Error: {e}"

    # ── Tool methods exposed to CAMEL ──────────────────────────────

    def list_files(self, path: str = "") -> str:
        """List files in the user's local project directory.

        Args:
            path: Optional sub-path relative to the project folder.
        """
        return self._dispatch("list_files", {"path": path, "project_id": self.api_task_id})

    def read_file(self, file_path: str) -> str:
        """Read the contents of a file from the user's local machine.

        Args:
            file_path: Path to the file (relative to project folder or absolute).
        """
        return self._dispatch("read_file", {"file_path": file_path})

    def file_exists(self, file_path: str) -> str:
        """Check if a file exists on the user's local machine.

        Args:
            file_path: Path to the file.
        """
        return self._dispatch("file_exists", {"file_path": file_path})

    def get_tools(self) -> list[FunctionTool]:
        return [
            FunctionTool(self.list_files),
            FunctionTool(self.read_file),
            FunctionTool(self.file_exists),
        ]
