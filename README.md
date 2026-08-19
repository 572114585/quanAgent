# DeepAgent — General-Purpose Task Agent

An extensible general-purpose task agent system built on DeepAgents / LangGraph. Ships with a Web UI, desktop and mobile shells, SSE streaming chat, human-in-the-loop (HITL) approval, file uploads, multi-channel bridging (WeChat / WeCom), pluggable Skills, multi-provider search failover, and SQLite-backed task plan persistence.

## Introduction

This project follows a "full-stack microservices + Skills" architecture. The core is a general-purpose agent orchestration kernel that is not bound to any specific business capability. Capabilities such as document extraction, web search, knowledge retrieval, data analysis, file processing, and PDF/Word/Excel generation are plugged in as Skills.

### Core Features

- 🤖 **General Agent Kernel** — built on DeepAgents, supports task planning, tool scheduling, and state management
- 🔌 **Pluggable Skills System** — MinerU document extraction, Word/Excel processing, Markdown-to-PDF, daily reports, editorial diagrams (`diagram-design`), web design, video presentation, and more
- 🌊 **SSE Streaming Response** — real-time streaming of conversation content, tool call status, and thinking process; thinking content and final answer are rendered separately
- 👤 **Human-in-the-Loop (HITL)** — high-risk shell (interpreter inline / network / install / unknown) needs confirm; **approve once for this call**; hard denies still apply
- 🛡️ **Tool-level permissions + workspace Auto** — writes auto-allowed in workspace; `execute` classified as `auto`/`ask`/`deny`; Plan mode plans only; channels deny dangerous tools
- 🪝 **Hooks** — before/after tool intercept (built-in permission + audit; injected into main + subagents; optional `workspace/hooks/*.py`)
- 📁 **Multimodal Support** — image and document (PDF / Word / Excel / Markdown) upload and parsing
- 📦 **Automatic Artifact Detection** — files generated during a conversation are auto-detected and pushed to the frontend
- 💬 **Multi-Channel Access** — WeChat and WeCom channel bridges
- 🖥️ **Cross-Platform Frontend** — Web + Desktop (Tauri 2) + Mobile, based on Vue 3 + TypeScript
- 🔧 **Configurable API URL** — backend address can be set dynamically from the frontend settings panel
- 🔐 **Command safety layer (not an OS sandbox)** — soft policy (bypass after HITL or auto class) + hard deny + write-path boundary + path rewriting; string policy, not OS process isolation
- 🧠 **Multi-LLM Provider** — switch between MiMo (current default), agnes, deepseek, and others via environment variables
- 🔎 **Multi-Provider Search Failover** — Tavily → Brave → Serper → DuckDuckGo, with 1-hour cooldown on quota errors and DuckDuckGo as the final fallback
- 💾 **SQLite Task Plan Persistence** — thread state (messages / todos / files / pending interrupts) survives process restarts; HITL resume works across restarts
- 🧩 **Subagent Observability** — `task()` calls stream `subagent_start` / `subagent_done` events with nested tool-call steps to the frontend task panel
- 🧭 **Auditable Research V2** — structured research contracts, dependency-aware units and budgets, global candidate pooling, provenance-preserving evidence/claim ledgers, weighted coverage, conflict/novelty supervision, and fail-closed citation verification

## Tech Stack

### Backend (Python)
- Python 3.10+
- FastAPI + uvicorn + sse-starlette (SSE service)
- DeepAgents + LangGraph (agent orchestration)
- LangChain (model & tool integration)
- `langgraph-checkpoint-sqlite` (thread state persistence)
- Optional: Langfuse (observability)

### Frontend
- Vue 3.5 + TypeScript 5.6
- Tauri 2 (cross-platform desktop / mobile)
- Vite 5.4 (build tooling)
- Tailwind CSS 3.4 (styling)
- Pinia 2.3 (state management)
- Vue Router 4.5 (routing)
- Reka UI 2 (headless UI primitives)
- marked + Shiki (Markdown rendering & code highlighting)
- DOMPurify (HTML sanitization)

## Quick Start

### Prerequisites

1. Python 3.10+
2. Node.js 20+
3. npm ≥ 10
4. Rust toolchain (required for desktop & mobile builds)
5. Platform-specific Tauri deps: https://tauri.app/start/prerequisites/

### Backend Startup

1. Install Python dependencies:

```bash
pip install -r requirement.txt
```

2. Configure environment variables (optional, create a `.env` file):

```env
# === LLM Provider switch (agnes | deepseek | sensenova | siliconflow | volcengine | mimo) ===
LLM_PROVIDER=agnes

# Xiaomi MiMo Token Plan (OpenAI-compatible; tp-xxxxx)
# LLM_PROVIDER=mimo
# MIMO_MODEL=mimo-v2.5-pro
# MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
# MIMO_API_KEY=your-mimo-token

# agnes config (default)
AGNES_MODEL=agnes-2.0-flash
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1/chat/completions
AGNES_API_KEY=your-agnes-key

# deepseek config (used when LLM_PROVIDER=deepseek)
# DEEPSEEK_MODEL=deepseek-chat
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_API_KEY=your-deepseek-key

# SiliconFlow (vision / object-sculptor): https://api-docs.siliconflow.cn/docs/api/chat-completions-post
# LLM_PROVIDER=siliconflow
# SILICONFLOW_API_KEY=your-siliconflow-key
# SILICONFLOW_MODEL=Qwen/Qwen3.6-35B-A3B
# SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
# LLM_SUPPORTS_VISION=true
# LLM_ENABLE_THINKING=false

# Volcengine Ark / Doubao (LLM_PROVIDER=volcengine|ark|doubao)
# VOLCENGINE_MODEL=doubao-seed-2.1-turbo
# VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3
# VOLCENGINE_API_KEY=your-ark-api-key

# === MinerU document extraction Skill (optional) ===
# MINERU_API_TOKEN=your-mineru-token
# MINERU_TOKEN=your-mineru-token

# === Search providers (leave blank to skip; failover: Tavily → Brave → Serper → DuckDuckGo) ===
TAVILY_API_KEY=
BRAVE_API_KEY=
SERPER_API_KEY=
SEARCH_PROVIDER_COOLDOWN_SECONDS=3600   # 1h cooldown after quota error

# === Service config ===
PORT=8000
HOST=0.0.0.0
HITL_ENABLED=true
MAX_UPLOAD_SIZE=20971520    # 20MB, in bytes
LOG_LEVEL=INFO

# === Agent mode & permissions (optional) ===
# AGENT_MODE=agent|plan
# EXECUTE_PROFILE=workspace_auto|manual   # default workspace_auto
# PERMISSION_EXECUTE=ask|allow|deny
# PERMISSION_WRITE=ask|allow|deny         # default allow
# CHANNEL_DENY_EXECUTE=true
# CLI --always-approve only when outer isolation (container/VM) already exists

# === Optional: Langfuse observability ===
# LANGFUSE_TRACING_ENABLED=true
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
# LANGFUSE_HOST=...
```

3. Start the backend:

```bash
python run.py
```

Service runs at `http://localhost:8000` by default.

**Backend API endpoints:**
- `GET /health` — health check
- `POST /upload` — file upload (images / documents)
- `POST /chat` — start / continue a conversation (returns SSE stream)
- `POST /chat/resume` — submit HITL approval decision after an interrupt
- `GET /uploads/<filename>` — static access to uploaded files
- `GET /output/<filename>` — static access to generated artifacts


### Frontend Startup

1. Enter the frontend directory:

```bash
cd agent-frontend
```

2. Install dependencies:

```bash
npm install
```

3. Start the dev server:

```bash
# Web dev mode
npm run dev

# Tauri desktop dev mode
npm run tauri:dev
```

4. Configure the backend URL:
   - Open the frontend app → Settings panel
   - Fill in API Base URL: `http://localhost:8000`
   - Save and start chatting

### Other Entry Points

- **Mock SSE service** (for frontend debugging):
  ```bash
  npm run mock:sse
  ```
- **WeChat channel**:
  ```bash
  python run_wechat.py
  ```
- **WeCom channel**:
  ```bash
  python run_wecom.py
  ```
- **Interactive CLI**:
  ```bash
  python demo.py
  ```

## Project Structure

```
d:\project
├── agent-frontend/              # Tauri + Vue frontend
│   ├── src/
│   │   ├── api/                 # ofetch client + SSE consumption
│   │   ├── components/
│   │   │   ├── chat/            # ChatPanel, MessageBubble, FloatingTodoList, HitlApproval
│   │   │   └── layout/          # AppShell, SessionItem, ThemeToggle
│   │   ├── composables/         # useMarkdown, usePlatform, useShortcuts, useTheme
│   │   ├── lib/                 # storage adapters (Tauri / IndexedDB)
│   │   ├── router/              # Vue Router config
│   │   ├── stores/              # Pinia stores (chat, sessions, settings)
│   │   ├── styles/              # global CSS + theme tokens
│   │   ├── types/               # shared TypeScript types (domain.ts)
│   │   └── views/               # HomeView, SessionView, SettingsView
│   ├── src-tauri/               # Tauri Rust shell
│   └── scripts/                 # generate-icons, mock-sse-server
├── agent_core/                  # agent core assembly package
│   ├── config.py                # unified config: paths, LLM/HITL/upload/search toggles
│   ├── llm.py                   # create_llm() + llm singleton
│   ├── prompts.py               # SYSTEM_PROMPT + section-writer definition
│   └── runtime.py               # build_agent() factory + agent singleton + DualSqliteSaver
├── sandbox/                     # ~1200-line shell sandbox (split from former agent_runtime.py)
│   ├── backend.py               # _SkillsShellBackend (path rewriting + encoding)
│   ├── whitelist.py             # _ShellWhitelistFilter (hard/soft deny) + assembled backend singleton
│   ├── trust.py                 # HITL approval trust-level ContextVar
│   ├── constants.py             # DEFAULT_ALLOWED_COMMANDS, _NODE_BUILD_COMMANDS, hard-deny patterns
│   └── path_rewriter.py         # shlex tokenization + token-level path rewriting
├── tools/                       # flat tool package
│   ├── web_search.py            # @tool web_search (uses tools/search/ failover chain)
│   ├── render_html.py           # @tool render_html
│   ├── get_current_time.py      # @tool get_current_time
│   └── search/                  # search provider abstraction
│       ├── base.py              # BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError
│       ├── tavily.py            # TavilyProvider
│       ├── brave.py             # BraveProvider
│       ├── serper.py            # SerperProvider
│       ├── duckduckgo.py        # DuckDuckGoProvider (fallback)
│       └── registry.py          # failover orchestration
├── artifacts/                   # unified artifact detection (eliminates former duplication)
│   └── detector.py              # snapshot_output_dir, detect_new_artifacts
├── entrypoints/                # entry implementations (root-level *.py are thin shims)
│   ├── web.py                   # FastAPI + SSE Web Bridge (delegated by run.py)
│   ├── cli.py                   # interactive terminal (delegated by demo.py)
│   ├── wechat.py               # WeChat channel (delegated by run_wechat.py)
│   └── wecom.py                # WeCom channel (delegated by run_wecom.py)
├── channels/                    # multi-channel bridging
│   ├── wechat/                  # WeChat channel (accounts, login, monitor, sender, ...)
│   └── wecom/                   # WeCom channel (client, handlers, bridge)
├── workspace/                  # agent sandbox root
│   ├── skills/                  # Skill definitions & implementations
│   │   ├── mineru/              # MinerU document extraction (PDF/image → Markdown)
│   │   ├── excel-xlsx/          # Excel processing
│   │   ├── word-docx/           # Word processing
│   │   ├── md-to-pdf/           # Markdown → PDF (multiple style recipes)
│   │   ├── daily-report/        # Daily report generation
│   │   ├── diagram-design/      # Editorial HTML/SVG diagrams (architecture, flowchart, …)
│   │   ├── web-design-engineer/ # Web design
│   │   └── web-video-presentation/ # Video presentation
│   ├── uploads/                 # user uploaded files
│   ├── output/                  # final delivered artifacts (visible to frontend)
│   ├── tmp/                     # intermediate temp files (not visible to frontend)
│   └── state/                   # SQLite checkpoints (checkpoints.sqlite)
├── tests/                       # test suite
├── run.py                       # thin shim → entrypoints/web.py
├── run_wechat.py                # thin shim → entrypoints/wechat.py
├── run_wecom.py                 # thin shim → entrypoints/wecom.py
├── demo.py                      # thin shim → entrypoints/cli.py
├── requirement.txt              # Python dependencies
├── README.md                    # this file (English)
├── README.zh-CN.md              # Chinese README
├── README_ARCHITECTURE.md       # architecture design document
├── AGENTS参考.md                # Agent design reference
└── deepagent指南.md              # DeepAgents usage guide
```

## Progress

### ✅ Completed

- [x] Backend FastAPI service framework
- [x] SSE streaming chat (`text/event-stream`) with async generators
- [x] DeepAgents integration with lazy-loaded singleton (init failure persisted as error state)
- [x] Frontend Vue 3 + Tauri 2 scaffolding
- [x] Chat UI & session management
- [x] Markdown rendering + code highlighting (Shiki)
- [x] File upload (images, PDF, Word, Excel, Markdown; 20MB limit)
- [x] Multimodal image input (with graceful fallback when model lacks vision)
- [x] HITL approval flow (high-risk `execute`; `web_search`/`web_fetch` default allow)
- [x] Frontend-configurable API Base URL
- [x] WeChat / WeCom channel bridging
- [x] Skills system (mineru, excel-xlsx, word-docx, md-to-pdf, daily-report, diagram-design, web-design-engineer, web-video-presentation)
- [x] **Thinking / final answer separation** — message-structure-based routing; `thinking_delta` → collapsible area, `delta` → main answer area
- [x] **Automatic artifact detection** — pre/post conversation diff of `output/`; new files pushed via `artifact` events
- [x] **Command safety layer** (`sandbox/` + `agent_core/execute_policy.py`):
  - **Workspace Auto**: readonly probes / readonly git / known build-test / skill scripts → auto-run
  - **Ask once**: `python -c` / `bash -c` / network / install / unknown → HITL; approve bypasses soft policy
  - **Hard deny** (never bypassed): command substitution, cwd escape, catastrophic patterns
  - Write-path boundary (`output/`/`tmp/` only) + path rewriting; Hooks injected into subagents
  - **Not** an OS-level process sandbox
- [x] Multi-LLM Provider switch (MiMo default / agnes / deepseek, etc.)
- [x] SSE ping keepalive (15s interval)
- [x] TypeScript SSE event handling (no default case in switch)
- [x] Langfuse observability integration (auto-degrades when unconfigured)
- [x] **Code reorganization** — root-level `agent_runtime.py` / `ducktools.py` / `html_tools.py` / `time_tools.py` split into `agent_core/`, `sandbox/`, `tools/`, `entrypoints/`, `artifacts/` packages; unified `build_agent()` factory eliminates the former three divergent agent configurations
- [x] **SQLite task plan persistence** — `DualSqliteSaver` (sync + async) replaces `BoundedMemorySaver`; thread state (messages / todos / files / pending interrupts) survives restarts; HITL resume works across restarts; WAL mode + busy_timeout + global lock for concurrent safety
- [x] **Multi-provider search failover** — `Tavily → Brave → Serper → DuckDuckGo` chain; providers with empty API keys are skipped; quota errors trigger 1-hour cooldown; non-quota errors skip without cooldown; DuckDuckGo as final fallback
- [x] **Subagent observability** — backend opens `subgraphs=True` and emits `subagent_start` / `subagent_done` SSE events with nested `tool_call` / `tool_result` steps (carrying `subagentId`); frontend `FloatingTodoList` renders per-`subagentId` cards with nested steps
- [x] **daily-report Skill** added to the Skill library
- [x] **diagram-design Skill** — editorial standalone HTML/SVG diagrams (architecture, flowchart, sequence, …)

### 🔧 In Progress / TODO

- [ ] Complete Skill registry & discovery mechanism
- [ ] More Skill implementations (PPT generation, data analysis, chart generation, etc.)
- [ ] Mobile adaptation polish
- [ ] User authentication & permission system
- [ ] Fast web search integration
- [ ] Production deployment (object storage, remote sandbox, etc.)

### 📋 Known Issues & Notes

- Frontend dev requires the backend SSE service to be running, otherwise messages won't display
- Python deps require `fastapi>=0.110`, `uvicorn[standard]>=0.27`, `sse-starlette>=2.0` for SSE support
- SSE streams must use `async def` generators and `agent.astream()`; otherwise the event loop blocks
- TypeScript must explicitly handle all SSE event types (no default case)
- **Path constraints**: agent writes can only land in `output/` or `tmp/`; `skills/` subtree is fully read-only; new skill scripts must be placed under `workspace/skills/<name>/scripts/` and require a service restart to take effect
- **HITL vs command policy**: default `EXECUTE_PROFILE=workspace_auto`. Routine local commands auto-run; approving a high-risk `execute` applies to that call and bypasses soft policy. Hard rules (command substitution, cwd escape, catastrophic patterns) still apply. `--always-approve` skips all asks (use only with outer isolation)
- **Path conventions**: SKILL.md may use `/skills/...`, `D:\skills\...`, or `skills/...` — the token-level rewriter unifies them to relative paths; when writing artifacts, you must use the `output/xxx` relative path
- **curl egress**: without approval only `api.openai.com` is allowed (TTS); after HITL approve other hosts may run; default TTS hosts live in `_CURL_ALLOWED_HOSTS`
- **Search providers**: at least one of Tavily / Brave / Serper should have an API key for the best experience; if all three are unconfigured, the chain falls back to DuckDuckGo only

## Architecture Document

For detailed architecture design, module responsibilities, and technology roadmap, see [README_ARCHITECTURE.md](file:///d:/project/README_ARCHITECTURE.md).

## Development Notes

### SSE Event Format

The frontend and backend communicate via SSE. Event types:

| Event | Description |
|-------|-------------|
| `start` | conversation start, includes messageId |
| `delta` | final-answer text increment (AIMessageChunk content without `tool_call_chunks`) |
| `thinking` | thinking-area start marker (heartbeat when no text output) |
| `thinking_delta` | thinking-process text increment (`reasoning_content` or tool-call round transitions; goes to collapsible area) |
| `tool_call` | model decides to call a tool (callId, name, args, optional `subagentId`); status = running |
| `tool_result` | tool execution result (callId, name, output, optional `subagentId`); status = completed |
| `subagent_start` | `task()` subagent launched (subagentId, subagentType, description) |
| `subagent_done` | `task()` subagent finished (subagentId) |
| `tool` | legacy compat event (degraded path; new code does not emit this) |
| `interrupt` | HITL interrupt awaiting user approval (toolCalls list) |
| `artifact` | new artifact file detected (name, path, url, mime, size) |
| `usage` | token usage stats |
| `ping` | keepalive (15s interval) |
| `done` | conversation end |
| `error` | error message |

**Thinking vs final answer separation mechanism** — based on message-structure routing, not on model output text markers:
- `reasoning_content` or tool-call round `content` → `thinking_delta` (frontend collapsible area)
- AIMessageChunk `content` without `tool_call_chunks` → `delta` (frontend main answer area)

**Subagent event semantics** — when the main agent invokes `task()`, the backend opens `subgraphs=True` and identifies subagent chunks via the langgraph namespace (`tools:<tid>`):
- On first subagent chunk → emit `subagent_start` (subagentId = base namespace)
- Subagent internal `ToolMessage`s → emit `tool_call` / `tool_result` carrying `subagentId`
- On parent `task()` ToolMessage → emit `subagent_done` and skip duplicate tool_call/tool_result

### Frontend Dev Commands

```bash
npm run dev              # Web dev
npm run build            # production build
npm run build:web        # Web mode build
npm run tauri:dev        # Tauri desktop dev
npm run tauri:build      # Tauri desktop build
npm run tauri:build:android   # Android build
npm run tauri:build:ios       # iOS build (macOS only)
npm run lint             # ESLint check & fix
npm run format           # Prettier format
```

## License

TBD
