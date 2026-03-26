 ---
  Eigent Technical Evaluation

  1. Auth System

  Short answer: There IS an auth system, but it's split across two components.

  Desktop backend (/backend/) — No auth at all. The local FastAPI server has
  zero authentication middleware. The middleware/__init__.py only registers i18n
   (BabelMiddleware). No JWT, no session tokens, no user validation on any
  endpoint. The router registers 5 controllers (health, chat, model, task, tool)
   with no auth guards. This makes sense for a local desktop app — it's talking
  to localhost.

  Cloud server (/server/) — Has auth infrastructure. The server component has:
  - domains/user/ — user management (api, schema, service layers)
  - domains/oauth/ — OAuth provider integration
  - core/oauth_adapter.py — OAuth flow handling
  - core/encrypt.py — credential encryption
  - core/redis_utils.py — likely session/cache store
  - Alembic migrations — persistent user database

  What this means for you: The cloud server auth exists but is clearly designed
  for Eigent's own SaaS offering (the "Cloud-Connected" deployment). If you
  fork, you'd need to either:
  - Use their cloud auth and extend it — adds dependency on their user system
  - Replace it with your own (e.g., Supabase Auth, which you already know) —
  cleaner but more work
  - Add auth to the desktop backend — if you want to gate local tool access
  behind login

  The password setup bug (#1494 — "greyed out for non-GitHub/Google accounts")
  suggests their email/password auth flow is incomplete. OAuth (GitHub/Google)
  is the primary path.

  Assessment: You'll need to build your own auth layer. Their auth is tightly
  coupled to their SaaS and not designed for white-labeling. But the Apache 2.0
  license lets you do this freely.

  2. Critical Issues

  101 open issues, 58 open PRs, 2 security alerts. Here's what matters:

  ┌──────────────────────────┬──────────┬───────────────────────────────────┐
  │          Issue           │ Severity │          Impact on Fork           │
  ├──────────────────────────┼──────────┼───────────────────────────────────┤
  │ #1510 "Impossible to     │ Critical │ Suggests onboarding/setup is      │
  │ use"                     │          │ fragile                           │
  ├──────────────────────────┼──────────┼───────────────────────────────────┤
  │ #1511 Groq API           │ High     │ Browser agent breaks with         │
  │ incompatibility          │          │ non-OpenAI providers              │
  ├──────────────────────────┼──────────┼───────────────────────────────────┤
  │ #1492 Model key config   │ High     │ Basic model setup failing for     │
  │ failed                   │          │ users                             │
  ├──────────────────────────┼──────────┼───────────────────────────────────┤
  │ #1494 Password setup     │ High     │ Email auth broken                 │
  │ greyed out               │          │                                   │
  ├──────────────────────────┼──────────┼───────────────────────────────────┤
  │ 2 security alerts        │ Unknown  │ Need investigation before         │
  │                          │          │ production use                    │
  ├──────────────────────────┼──────────┼───────────────────────────────────┤
  │ #1478 HTML rendering     │ Medium   │ UI reliability issue              │
  │ failed                   │          │                                   │
  └──────────────────────────┴──────────┴───────────────────────────────────┘

  The pattern is concerning: basic setup flows are broken (model config, auth,
  usability). This is a young project with 13.2k stars but rough edges. The
  sprint-based milestones (Sprint 19, 20) suggest active development, but
  quality is inconsistent.

  Assessment: Fork risk is moderate. The core agent architecture works, but the
  edges are rough. You'd be inheriting bugs and technical debt. However, 13.2k
  stars and 1.5k forks means the community is large enough to expect continued
  development.

  3. Orchestration Capabilities

  Agent Types (8 specialized agents):
  - Task Agent (coordinator/decomposer)
  - Developer Agent (code execution, terminal)
  - Browser Agent (web search, scraping)
  - Document Agent (file creation/management)
  - Multi-Modal Agent (images, audio)
  - MCP Agent (MCP server tools)
  - Social Media Agent
  - Task Summary Agent

  Orchestration model:
  - Task decomposition: A coordinator agent breaks tasks into subtasks, assigns
  to specialized agents
  - Queue-based coordination: asyncio.Queue per task, agents communicate via
  event queue
  - HITL: human_input[agent] queues — when an agent needs user input, it pauses
  and waits
  - Parallel execution: Multiple background_tasks tracked per TaskLock, agents
  can run concurrently
  - Streaming: Real-time SSE streaming of agent progress to frontend
  - Lifecycle management: Activate/deactivate agents and toolkits dynamically
  during task execution

  MCP Integration:
  - Uses CAMEL's MCPToolkit with 180-second connection timeout
  - MCP servers configured via installed_mcp['mcpServers'] JSON config
  - Dedicated MCP Agent type that loads tools dynamically from connected servers
  - Tool name mapping via get_function_name()
  - Auth credentials stored in ~/.mcp-auth/ (MD5-hashed)
  - Built-in tool management for Notion, Google Calendar, LinkedIn — with
  install/uninstall/status endpoints

  Can you easily install MCPs and skills for clients?

  Yes, the architecture supports it:
  - MCP servers are configured as JSON (mcpServers config object)
  - The tool_controller.py has install/uninstall endpoints
  - You could build a "construction pack" installer that pushes MCP configs
  programmatically

  What's missing vs. Furnace:
  - No per-client isolation (it's a single-user desktop app)
  - No Supabase choreography bus (uses in-memory queues)
  - No container-based agent isolation (agents are in-process)
  - No audit trail / execution traces (basic logging only, OpenTelemetry
  partially set up)
  - No multi-tenant anything

  Overall Assessment

  ┌─────────────────┬───────────┬───────────────────────────────────────────┐
  │    Dimension    │  Rating   │                   Notes                   │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Auth            │ Weak      │ Cloud auth exists but incomplete; desktop │
  │                 │           │  has none. You'd build your own.          │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Stability       │ Moderate  │ Core works, edges are rough. Active       │
  │                 │           │ development but quality inconsistent.     │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ MCP Support     │ Strong    │ Native CAMEL MCPToolkit,                  │
  │                 │           │ install/uninstall flows, dynamic loading. │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Orchestration   │ Good      │ Multi-agent decomposition, HITL, parallel │
  │                 │           │  execution, streaming.                    │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Extensibility   │ Good      │ Factory pattern, clean agent/toolkit      │
  │                 │           │ separation, easy to add agent types.      │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ License         │ Excellent │ Apache 2.0 — full commercial fork rights  │
  │                 │           │ with attribution.                         │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Community       │ Strong    │ 13.2k stars, 1.5k forks, active sprints.  │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Enterprise      │ Weak      │ No multi-tenancy, no audit trails, no     │
  │ readiness       │           │ client isolation.                         │
  ├─────────────────┼───────────┼───────────────────────────────────────────┤
  │ Fork viability  │ Moderate  │ Clean architecture but you'd need to add  │
  │                 │           │ auth, telemetry, and client management.   │
  └─────────────────┴───────────┴───────────────────────────────────────────┘