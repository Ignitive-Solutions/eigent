// ========= Copyright 2025-2026 @ Eigent.ai All Rights Reserved. =========

import { useAuthStore } from '@/store/authStore';
import { useCallback, useRef } from 'react';

interface ToolRequestMessage {
  type: 'tool_request';
  request_id: string;
  action: string;
  params: Record<string, any>;
  user_id: string;
  project_id?: string;
  timestamp: string;
}

/** Whitelist of actions the Electron app is allowed to execute. */
const ALLOWED_ACTIONS = new Set([
  'list_files',
  'read_file',
  'file_exists',
]);

async function handleListFiles(params: {
  path?: string;
  project_id: string;
}): Promise<any> {
  const authStore = useAuthStore.getState();
  if (!authStore.email) {
    throw new Error('User not authenticated');
  }
  return await window.ipcRenderer.invoke(
    'get-project-file-list',
    authStore.email,
    params.project_id,
  );
}

async function handleReadFile(params: {
  file_path: string;
  max_size?: number;
}): Promise<string> {
  const maxSize = params.max_size ?? 100_000;
  const content: string = await window.ipcRenderer.invoke(
    'read-file',
    params.file_path,
  );
  if (content.length > maxSize) {
    return content.substring(0, maxSize) + '\n... (truncated)';
  }
  return content;
}

async function handleFileExists(params: {
  file_path: string;
}): Promise<boolean> {
  try {
    await window.ipcRenderer.invoke('read-file', params.file_path);
    return true;
  } catch {
    return false;
  }
}

const ACTION_HANDLERS: Record<
  string,
  (params: any) => Promise<any>
> = {
  list_files: handleListFiles,
  read_file: handleReadFile,
  file_exists: handleFileExists,
};

/**
 * Hook that handles local-action tool requests arriving over the WebSocket.
 * Call `handleToolRequest(message)` when a `tool_request` message arrives.
 */
export function useLocalActionHandler(
  wsRef: React.RefObject<WebSocket | null>,
) {
  const handleToolRequest = useCallback(
    async (message: ToolRequestMessage) => {
      const { request_id, action, params } = message;
      const ws = wsRef.current;

      if (!ws || ws.readyState !== WebSocket.OPEN) {
        console.error(
          '[LocalAction] Cannot respond — WebSocket not connected',
        );
        return;
      }

      if (!ALLOWED_ACTIONS.has(action)) {
        sendResponse(ws, request_id, false, null, `Action '${action}' is not allowed`);
        return;
      }

      console.log('[LocalAction] Executing:', action, request_id);

      try {
        const handler = ACTION_HANDLERS[action];
        const result = await handler(params);
        sendResponse(ws, request_id, true, result);
        console.log('[LocalAction] Success:', action, request_id);
      } catch (error: any) {
        console.error('[LocalAction] Error:', action, error);
        sendResponse(
          ws,
          request_id,
          false,
          null,
          error?.message || 'Unknown error',
        );
      }
    },
    [wsRef],
  );

  return { handleToolRequest };
}

function sendResponse(
  ws: WebSocket,
  request_id: string,
  success: boolean,
  result: any,
  error?: string,
) {
  ws.send(
    JSON.stringify({
      type: 'tool_response',
      request_id,
      success,
      result,
      error,
      timestamp: new Date().toISOString(),
    }),
  );
}
