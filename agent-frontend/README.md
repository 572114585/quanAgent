# Agent Frontend

Cross-platform frontend for the agent runtime. Single Vue 3 codebase, shipped as:

- **Web** — static SPA, deploy to any CDN
- **Desktop** — Tauri 2 native shell for Windows / macOS / Linux
- **Mobile** — Tauri 2 native shell for Android / iOS

## Tech Stack

| Layer        | Choice                                                |
| ------------ | ----------------------------------------------------- |
| Framework    | Vue 3.5 + TypeScript 5.6 + Vite 5.4                    |
| State        | Pinia 2.3                                             |
| Routing      | Vue Router 4.5                                        |
| Styling      | Tailwind CSS 3.4 + CSS variable theme tokens          |
| UI Primitives| Reka UI 2 (headless, accessible)                      |
| Icons        | lucide-vue-next                                       |
| Markdown     | marked 14 + shiki 1                                   |
| HTTP         | ofetch 1.5                                            |
| Shell        | Tauri 2 (desktop + mobile targets)                    |

## Prerequisites

- Node.js ≥ 20
- npm ≥ 10
- Rust toolchain (`rustup` + `cargo`) — required for desktop & mobile builds
- Platform-specific Tauri deps: https://tauri.app/start/prerequisites/
- Android SDK + NDK for Android builds
- Xcode 15+ for iOS builds (macOS only)

## Getting Started

```bash
# install
npm install

# run web dev server (http://localhost:1420)
npm run dev

# build static web bundle to ./dist
npm run build:web

# run as Tauri desktop app (requires Rust)
npm run tauri:dev

# build desktop installers
npm run tauri:build

# build Android (requires ANDROID_HOME + NDK)
npm run tauri:build:android

# build iOS (macOS + Xcode only)
npm run tauri:build:ios
```

## Project Layout

```
agent-frontend/
├── src/                     # Vue 3 application
│   ├── api/                 # ofetch client + endpoint modules
│   ├── components/
│   │   ├── chat/            # ChatPanel, message bubbles, composer
│   │   ├── layout/          # AppShell, Sidebar, ThemeToggle
│   │   └── ui/              # Reka UI wrappers
│   ├── composables/         # useTheme, usePlatform, useChat, useSSE
│   ├── router/              # Vue Router config
│   ├── stores/              # Pinia stores (sessions, messages, settings)
│   ├── styles/              # Global CSS + theme variables
│   ├── types/               # Shared TypeScript types
│   ├── views/               # Route-level components
│   ├── App.vue
│   └── main.ts
├── src-tauri/               # Rust shell (Tauri 2)
│   ├── src/
│   │   ├── main.rs
│   │   └── lib.rs           # Plugin registration, commands
│   ├── capabilities/        # Tauri permission manifests
│   ├── icons/               # App icons
│   ├── Cargo.toml
│   ├── tauri.conf.json
│   └── build.rs
├── scripts/
│   └── generate-icons.py    # Placeholder icon generator
├── public/
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── postcss.config.cjs
└── package.json
```

## Phase Progress

- [x] **Phase 1** — Scaffolding (Vue 3 + Vite + Tauri 2 + Tailwind, base layout, theme system, placeholder chat)
- [x] **Phase 2** — Core UI refinement & theme polish
- [x] **Phase 3** — Chat + SSE streaming (real backend integration via [run.py](../run.py))
- [ ] **Phase 4** — Session history persistence
- [ ] **Phase 5** — File/attachment upload polish
- [ ] **Phase 6** — Mobile native integration
- [ ] **Phase 7** — Web build optimization

## Connecting to the Agent Backend

The frontend talks to the Python bridge service in [run.py](../run.py), which wraps your `agent_runtime.create_deep_agent`. Three endpoints are exposed:

| Method | Path             | Purpose                                |
| ------ | ---------------- | -------------------------------------- |
| POST   | `/chat`          | Send a message, receive SSE stream     |
| POST   | `/chat/resume`   | Continue after HITL tool-call approval |
| POST   | `/upload`        | Upload a file, get back a URL          |
| GET    | `/uploads/*`     | Static file serving                    |
| GET    | `/health`        | Health check                           |

### Start the backend

```bash
cd d:\project
pip install -r requirement.txt   # one-time
python run.py                    # default: http://localhost:8000
```

Optional env vars:
- `PORT=9000` — change port
- `HOST=0.0.0.0` — bind address (default)
- `HITL_ENABLED=false` — disable Human-in-the-Loop tool approval

### Start the frontend

```bash
cd d:\project\agent-frontend
npm install
npm run dev
```

Open `http://localhost:1420/`, then in **Settings** set:
- API Base URL → `http://localhost:8000`
- Stream → on

Send a message — you should see the agent respond through the bridge.

### HITL flow

When the agent wants to call a tool that requires approval, the backend sends an
`interrupt` SSE event with `toolCalls`. The frontend renders an approval card
with Approve / Reject buttons. On click, the frontend POSTs the decisions to
`/chat/resume` and the stream continues.

## Mock SSE Service (dev only)

If you want to develop the frontend without the Python backend:

```bash
npm run mock:sse   # starts a stub on http://localhost:8787
```

Point the API Base URL to `http://localhost:8787` in Settings.

## Replacing Placeholder Icons

```bash
# drop your 1024x1024 source PNG at scripts/source-icon.png
python scripts/generate-icons.py
```

## Mock SSE Service

Phase 3 ships a tiny Node-based mock backend so you can verify the chat + SSE
flow without a real agent runtime. It listens on `http://localhost:8787` and
streams a multi-segment Markdown reply to `POST /chat`.

```bash
# in one terminal
npm run mock:sse

# in another terminal — point the app at it via Settings → API Base URL
# http://localhost:8787
npm run dev

# or smoke-test directly
curl -N -X POST http://localhost:8787/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"demo","message":"hello"}'
```

The mock emits `start` → several `delta` chunks (80–150ms apart) → `usage` →
`done`, matching the `StreamEvent` type in `src/types/domain.ts`. To talk to
your real backend, change the Base URL in Settings (or set
`VITE_API_BASE_URL` at build time).

## License

Internal.
