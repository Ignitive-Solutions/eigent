Architecture: Hybrid AI Orchestration Platform for Construction

1. Executive Summary

This document outlines the architecture for adapting the open-source Eigent orchestration engine into a proprietary, multi-tenant SaaS platform (codename: Ignitive).

The core objective is to deliver AI-driven construction workflows to clients while satisfying three constraints:

- IP Protection: Proprietary agent skills, prompts, and MCP servers are hidden from the end-user.
- Centralized Telemetry: All agent activity is logged centrally for monitoring and billing.
- Native Windows Execution: The platform interacts with local Windows tools (Microsoft Office via COM automation) without server-side licensing violations.

The platform uses a decoupled architecture: a Cloud-hosted "Brain" and a Locally installed "Muscle" (Dumb Client).


2. System Architecture

2.1 The Cloud Layer (The "Brain")

Hosted on a DigitalOcean droplet (Ubuntu + Docker), accessible at eigent-dev.ignitive.ai.

Two containerized services behind a reverse proxy:

- API Server (Eigent /server/ component): Handles authentication (JWT), session management, user/tenant data, trigger scheduling (Celery/Beat), and acts as the gateway for all client requests. PostgreSQL for persistence, Redis for sessions/rate-limiting/token blacklist.

- Orchestration Worker (Eigent /backend/ component): Runs the CAMEL-based multi-agent engine — task decomposition, agent workforce management, tool execution, and LLM routing. Receives chat requests proxied from the API Server. Streams results back via SSE.

This is an incremental split: the existing proxy mode already supports the Server forwarding requests to a separate backend. As tenants scale, the worker evolves into a horizontally-scaled pool dispatched via Redis pub/sub, but the initial deployment is a simple two-container setup.

- Central Database (PostgreSQL): Stores users, chat histories, agent configurations, trigger executions, and telemetry logs.

- Proprietary Resources: SKILL.md files (system prompts) and MCP server configurations live exclusively on the cloud, never shipped to clients.

2.2 The Local Layer (The "Muscle")

Installed on the client's local Windows machine.

- Frontend UI (Electron/React): The Eigent desktop app configured in proxy mode — VITE_PROXY_URL points to eigent-dev.ignitive.ai. It is purely a presentation layer; all reasoning happens in the cloud.

- Local Execution Engine: A lightweight background service (bundled inside Electron) that:
  - Maintains a persistent WebSocket connection to the API Server
  - Receives JSON action payloads (e.g., {"action": "run_excel_macro", "params": {...}})
  - Executes predefined scripts against the local OS (win32com for Excel/Word)
  - Returns success/failure results back up the WebSocket
  - Performs zero LLM calls — no API keys, no prompts, no agent logic on the client

2.3 The Communication Bridge

- Transport: Persistent WebSocket connections initiated by the local client, bypassing corporate inbound firewalls.
- Protocol: The cloud agent perceives the client's local machine as an MCP tool. The API Server's existing WebSocket session manager (Redis-backed, with delivery confirmation) is extended to support local action dispatch alongside trigger execution events.


3. Execution Flow

When a client requests: "Update the construction schedule in my local Excel file and draft a summary report":

1. Authentication — Client opens Electron app, authenticates via JWT against the API Server. A WebSocket tunnel is established.

2. Reasoning — The prompt is forwarded from the API Server to the Orchestration Worker. The CAMEL workforce decomposes the task using proprietary SKILL.md prompts. All LLM calls happen server-side.

3. Remote Tool Execution — If the agent needs cloud-based data (construction APIs, databases), it uses cloud-hosted MCP servers. All processing stays on the server.

4. Local Command Dispatch — The agent calls a local execution MCP tool (e.g., execute_local_action). The API Server looks up the client's active WebSocket session and pushes the JSON payload down the tunnel.

5. Native Execution — The Local Execution Engine receives the payload, maps it to a predefined handler, triggers Excel.exe via COM automation, and captures the result.

6. Confirmation & Telemetry — The result travels back up the WebSocket. The API Server logs the full transaction (tokens, tool calls, success/failure, duration) to PostgreSQL for the telemetry dashboard.


4. Implementation Phases

Phase 1: Cloud Deployment & Decoupling
Deploy the two-container architecture (API Server + Orchestration Worker) on the DigitalOcean droplet with Docker Compose. Set up PostgreSQL, Redis, Celery. Configure Nginx/Caddy as reverse proxy with TLS for eigent-dev.ignitive.ai. Update CORS and frontend env vars. Validate that the Electron app in proxy mode can authenticate and run agent workflows against the cloud.

Phase 2: WebSocket Local Action Bridge
Extend the API Server's existing WebSocket session manager to support bidirectional local action dispatch. Define an MCP tool schema (execute_local_action) that the cloud agent can call. Build a WebSocket listener in the Electron main process with a secure handler registry mapping action types to local scripts. Implement delivery confirmation and timeout handling using the existing Redis-backed session infrastructure.

Phase 3: Local Executor & Packaging
Write Windows automation handlers (Python win32com wrappers for Excel, Word, file system operations). Compile into standalone executables via PyInstaller. Bundle inside the Electron build so clients install a single .exe/.msi. Implement a whitelist of allowed actions for security — the executor only runs pre-registered handlers, never arbitrary code.

Phase 4: Admin Telemetry & Monitoring
Build admin API endpoints aggregating telemetry from PostgreSQL (tokens per client, execution rates, error rates, tool usage). Develop an internal React admin portal (separate from the Electron client). Track: client usage for billing, WebSocket health/error rates, and anonymized chat histories for prompt refinement.


5. Security & IP Protection

- Proprietary Logic: All agent prompts, SKILL.md files, and MCP configurations live exclusively on the cloud. The Electron client ships zero proprietary logic.
- Access Control: JWT-based auth with Redis token blacklist. Subscription lapse → WebSocket refused → all tools revoked instantly.
- Local Executor Safety: Whitelist-only execution — the local engine runs only pre-registered action handlers, never arbitrary code from the cloud. Each action is logged and auditable.
- Client Data: The local executor acts only on files explicitly targeted by the workflow. Heavy processing stays in cloud memory; only final formatted data is pushed to the client.
