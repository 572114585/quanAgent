# DeepAgent 通用任务 Agent

一个基于 DeepAgents / LangGraph 构建的可扩展通用任务 Agent 系统，支持 Web 界面、桌面应用和移动端，具备 SSE 流式对话、人机协作（HITL）、文件上传、多渠道接入（微信 / 企业微信）、可插拔 Skills、多搜索 Provider 失败回退、SQLite 任务计划持久化等能力。

## 项目介绍

本项目采用"全链路微服务 + Skills"架构，核心是一个通用 Agent 编排内核，不绑定具体业务能力。文档提取、联网搜索、知识库检索、数据分析、文件处理、PDF/Word/Excel 生成等能力以可插拔 Skill 形式接入。

### 核心特性

- 🤖 **通用 Agent 内核**：基于 DeepAgents，支持任务规划、工具调度、状态管理
- 🔌 **可插拔 Skills 系统**：MinerU 文档提取、Word/Excel 处理、Markdown 转 PDF、日报、编辑级图表（`diagram-design`）、网页设计、视频演示等技能扩展
- 🌊 **SSE 流式响应**：实时推送对话内容、工具调用状态、思考过程，思考与最终答案分离渲染；事件契约 `schemaVersion: 1`（与 CLI `--format streaming-json` 共用）
- 👤 **人机协作（HITL）**：高风险 shell（解释器内联 / 联网 / 安装 / 未知命令）需确认；**批准仅针对本次调用**；硬拒绝仍不可绕过
- 🛡️ **工具级权限 + 工作区 Auto**：`write_file`/`edit_file` 默认放行；`execute` 按命令 `auto`/`ask`/`deny` 分类；Plan 模式只规划；渠道默认 deny 危险工具
- 🪝 **Hooks**：工具调用前后拦截（内置权限强制 + 审计；主图与子 agent 均注入；可选 `workspace/hooks/*.py`）
- 📁 **多模态支持**：图片、文档（PDF / Word / Excel / Markdown）上传与解析
- 📦 **产物自动检测**：对话过程中生成的文件自动检测并推送给前端
- 💬 **多渠道接入**：微信、企业微信渠道桥接
- 🖥️ **跨平台前端**：Web + 桌面（Tauri 2）+ 移动端，基于 Vue 3 + TypeScript
- 🔧 **可配置 API 地址**：前端设置面板可动态配置后端服务地址
- 🔐 **命令安全层（非 OS 沙盒）**：软策略（HITL 批准或 auto 可绕过）+ 硬拒绝 + 写路径边界 + 路径改写；当前是字符串策略，不是 OS 进程隔离
- 🧠 **多 LLM Provider**：支持 MiMo（当前默认）/ agnes / deepseek 等，通过环境变量切换
- 🔎 **多搜索 Provider 失败回退**：Tavily → Brave → Serper → DuckDuckGo，额度错误冷却 1 小时，DuckDuckGo 兜底
- 💾 **SQLite 任务计划持久化**：thread 状态（messages / todos / files / pending interrupts）跨进程重启可恢复，HITL resume 跨重启生效
- 🧩 **子智能体可观测性**：`task()` 调用通过 `subagent_start` / `subagent_done` 事件把子智能体任务及其嵌套工具调用步骤流式推送给前端任务面板
- 🧭 **可审计 Research V2**：结构化研究契约、带依赖与独立预算的研究单元、全局候选池、保留溯源的证据/主张账本、加权覆盖率、冲突/新颖性监督，以及 fail-closed 引用校验

## 技术栈

### 后端（Python）
- Python 3.10+
- FastAPI + uvicorn + sse-starlette（SSE 服务）
- DeepAgents + LangGraph（Agent 编排）
- LangChain（模型与工具集成）
- `langgraph-checkpoint-sqlite`（thread 状态持久化）
- 可选：Langfuse（可观测性）

### 前端
- Vue 3.5 + TypeScript 5.6
- Tauri 2（跨平台桌面 / 移动端）
- Vite 5.4（构建工具）
- Tailwind CSS 3.4（样式）
- Pinia 2.3（状态管理）
- Vue Router 4.5（路由）
- Reka UI 2（无障碍无样式 UI 基元）
- marked + Shiki（Markdown 渲染 & 代码高亮）
- DOMPurify（HTML 清洗）

## 快速开始

### 环境准备

1. Python 3.10+
2. Node.js 20+
3. npm ≥ 10
4. Rust 工具链（桌面 / 移动端构建必需）
5. 各平台 Tauri 依赖：https://tauri.app/start/prerequisites/

### 后端启动

1. 安装 Python 依赖：

```bash
pip install -r requirement.txt
```

2. 配置环境变量（可选，创建 `.env` 文件）：

```env
# === LLM Provider 切换（agnes | deepseek | sensenova | siliconflow | volcengine | mimo）===
LLM_PROVIDER=agnes

# 小米 MiMo Token Plan（OpenAI 兼容；tp-xxxxx）
# LLM_PROVIDER=mimo
# MIMO_MODEL=mimo-v2.5-pro
# MIMO_BASE_URL=https://token-plan-cn.xiaomimimo.com/v1
# MIMO_API_KEY=your-mimo-token

# agnes 配置（默认）
AGNES_MODEL=agnes-2.0-flash
AGNES_BASE_URL=https://apihub.agnes-ai.com/v1/chat/completions
AGNES_API_KEY=your-agnes-key

# deepseek 配置（LLM_PROVIDER=deepseek 时使用）
# DEEPSEEK_MODEL=deepseek-chat
# DEEPSEEK_BASE_URL=https://api.deepseek.com
# DEEPSEEK_API_KEY=your-deepseek-key

# 硅基流动（视觉 / object-sculptor）：https://api-docs.siliconflow.cn/docs/api/chat-completions-post
# LLM_PROVIDER=siliconflow
# SILICONFLOW_API_KEY=your-siliconflow-key
# SILICONFLOW_MODEL=Qwen/Qwen3.6-35B-A3B
# SILICONFLOW_BASE_URL=https://api.siliconflow.cn/v1
# LLM_SUPPORTS_VISION=true
# LLM_ENABLE_THINKING=false

# 火山方舟 / 豆包（LLM_PROVIDER=volcengine，别名 ark/doubao）
# VOLCENGINE_MODEL=doubao-seed-2.1-turbo
# VOLCENGINE_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3
# VOLCENGINE_API_KEY=your-ark-api-key

# === MinerU 文档提取 Skill（可选）===
# MINERU_API_TOKEN=your-mineru-token
# MINERU_TOKEN=your-mineru-token

# === 搜索 Provider（留空则跳过；failover 链路：Tavily → Brave → Serper → DuckDuckGo）===
TAVILY_API_KEY=
BRAVE_API_KEY=
SERPER_API_KEY=
SEARCH_PROVIDER_COOLDOWN_SECONDS=3600   # 额度错误后冷却 1 小时

# === 服务配置 ===
PORT=8000
HOST=0.0.0.0
HITL_ENABLED=true
MAX_UPLOAD_SIZE=20971520    # 20MB，单位字节
LOG_LEVEL=INFO

# === Agent 模式与权限（可选）===
# AGENT_MODE=agent|plan          # 默认 agent；plan 只规划不写/不 shell
# EXECUTE_PROFILE=workspace_auto|manual  # 默认 workspace_auto
# PERMISSION_EXECUTE=ask|allow|deny   # 工具级；workspace_auto 下再按命令细分
# PERMISSION_WRITE=ask|allow|deny     # 默认：allow（工作区内写 tmp/output）
# CHANNEL_DENY_EXECUTE=true           # 微信/企微默认拒绝 execute
# HOOKS_DIR=workspace/hooks           # 可选脚本 hooks 目录
# CLI --always-approve 仅建议在外层已有容器/虚拟机隔离时使用

# === 可选：Langfuse 可观测性 ===
# LANGFUSE_TRACING_ENABLED=true
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
# LANGFUSE_HOST=...
```

3. 启动后端服务：

```bash
python run.py
```

服务默认运行在 `http://localhost:8000`。

**后端 API 端点：**
- `GET /health` — 健康检查（含 `schema_version` / `agent_mode_default`）
- `POST /upload` — 文件上传（图片 / 文档）
- `POST /chat` — 发起 / 继续对话（返回 SSE 流；请求体可选 `mode: agent|plan`）
- `POST /chat/resume` — HITL 中断后提交审批决定（可选 `mode`）
- `GET /uploads/<filename>` — 上传文件静态访问
- `GET /output/<filename>` — 生成产物静态访问

### 可审计 Research V2

`POST /research` 创建可持久恢复的研究任务。研究契约可声明决策用途、受众、时间范围、地域、术语定义、必答维度、排除项、来源偏好、输出 schema 与明确的输出要求。deep/wide 模式必须在定向检索后修订并批准计划，才能进入正式采集；研究单元支持重要性权重、前置依赖、验收标准、必需来源类型、开放缺口和独立的搜索/抓取预算。

研究工作台和 `GET /research/{run_id}` 同时展示加权/未加权覆盖率、来源质量、未使用证据与新颖性队列、重复来源簇、主张冲突和引用链。高优先级缺口、必需来源类型、未决冲突或无支撑的重要主张存在时，报告就绪判定保持 fail-closed。

主要接口还包括 `GET /research/{run_id}/sources`、`/claims`、`/passages`、`/advanced`，以及 `POST /research/{run_id}/plan/revise`、`/approve`、`/verify`、`/control`。持久状态位于 `workspace/state/research/<run_id>/`。

可复现评测适配器位于 `evals/`。已下载公开数据集后可运行：

```bash
```

DRB2 适配器只把公开任务与禁用来源清单交给规划器；隐藏 rubric 标签仅用于生成后的评估，避免评测泄漏。

**CLI（可选）：**

```bash
python demo.py                              # 交互文本
python demo.py --mode plan                  # 只规划
python demo.py --format streaming-json -p "解释本仓库"   # NDJSON 无头（schemaVersion=1）
python demo.py --always-approve -p "列出 skills"
```

### 前端启动

1. 进入前端目录：

```bash
cd agent-frontend
```

2. 安装依赖：

```bash
npm install
```

3. 启动开发服务器：

```bash
# Web 开发模式
npm run dev

# Tauri 桌面开发模式
npm run tauri:dev
```

4. 配置后端地址：
   - 打开前端应用 → 设置面板
   - 填写 API Base URL：`http://localhost:8000`
   - 保存后即可开始对话

### 其他启动方式

- **Mock SSE 服务**（前端调试用）：
  ```bash
  npm run mock:sse
  ```
- **微信渠道**：
  ```bash
  python run_wechat.py
  ```
- **企业微信渠道**：
  ```bash
  python run_wecom.py
  ```
- **交互式 CLI**：
  ```bash
  python demo.py
  ```

## 项目结构

```
d:\project
├── agent-frontend/              # Tauri + Vue 前端
│   ├── src/
│   │   ├── api/                 # ofetch 客户端 + SSE 消费
│   │   ├── components/
│   │   │   ├── chat/            # ChatPanel, MessageBubble, FloatingTodoList, HitlApproval
│   │   │   └── layout/          # AppShell, SessionItem, ThemeToggle
│   │   ├── composables/         # useMarkdown, usePlatform, useShortcuts, useTheme
│   │   ├── lib/                 # 存储适配（Tauri / IndexedDB）
│   │   ├── router/              # Vue Router 配置
│   │   ├── stores/              # Pinia 状态管理（chat, sessions, settings）
│   │   ├── styles/              # 全局样式 + 主题 token
│   │   ├── types/               # 共享 TypeScript 类型（domain.ts）
│   │   └── views/               # HomeView, SessionView, SettingsView
│   ├── src-tauri/               # Tauri Rust 壳
│   └── scripts/                 # generate-icons, mock-sse-server
├── agent_core/                  # agent 核心装配包
│   ├── config.py                # 统一配置：路径常量 + LLM/HITL/上传/搜索开关
│   ├── llm.py                   # create_llm() + llm 单例
│   ├── prompts.py               # SYSTEM_PROMPT + section-writer 定义
│   └── runtime.py               # build_agent() 工厂 + agent 单例 + DualSqliteSaver
├── sandbox/                     # ~1200 行 Shell 沙箱（从原 agent_runtime.py 拆出）
│   ├── backend.py               # _SkillsShellBackend（路径改写 + 编码兼容）
│   ├── whitelist.py             # _ShellWhitelistFilter（硬/软拒绝）+ 组装 backend 单例
│   ├── trust.py                 # HITL 批准信任级别 ContextVar
│   ├── constants.py             # DEFAULT_ALLOWED_COMMANDS, _NODE_BUILD_COMMANDS, 硬拒绝模式
│   └── path_rewriter.py         # shlex 分词 + token 级路径改写函数
├── tools/                       # 扁平工具包
│   ├── web_search.py            # @tool web_search（走 tools/search/ failover 链路）
│   ├── render_html.py           # @tool render_html
│   ├── get_current_time.py      # @tool get_current_time
│   └── search/                  # 搜索 Provider 抽象层
│       ├── base.py              # BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError
│       ├── tavily.py            # TavilyProvider
│       ├── brave.py             # BraveProvider
│       ├── serper.py            # SerperProvider
│       ├── duckduckgo.py        # DuckDuckGoProvider（兜底）
│       └── registry.py          # failover 编排
├── artifacts/                   # 产物检测统一模块（消除原 run.py 与 wechat bridge 的重复实现）
│   └── detector.py              # snapshot_output_dir, detect_new_artifacts
├── entrypoints/                # 入口实现（根级 *.py 均为薄 shim）
│   ├── web.py                   # FastAPI + SSE Web Bridge（run.py 委派）
│   ├── cli.py                   # 交互式终端（demo.py 委派）
│   ├── wechat.py               # 微信渠道（run_wechat.py 委派）
│   └── wecom.py                # 企业微信渠道（run_wecom.py 委派）
├── channels/                    # 多渠道桥接
│   ├── wechat/                  # 微信渠道（accounts, login, monitor, sender, ...）
│   └── wecom/                   # 企业微信渠道（client, handlers, bridge）
├── workspace/                  # Agent 沙箱根目录
│   ├── skills/                  # Skill 定义与实现
│   │   ├── mineru/              # MinerU 文档提取（PDF/图片 → Markdown）
│   │   ├── excel-xlsx/          # Excel 处理
│   │   ├── word-docx/           # Word 处理
│   │   ├── md-to-pdf/           # Markdown 转 PDF（含多套样式配方）
│   │   ├── daily-report/        # 日报生成
│   │   ├── diagram-design/      # 编辑级 HTML/SVG 图表（架构图、流程图等）
│   │   ├── web-design-engineer/ # 网页设计
│   │   └── web-video-presentation/ # 视频演示
│   ├── uploads/                 # 用户上传文件存储
│   ├── output/                  # 最终交付产物输出（前端可见）
│   ├── tmp/                     # 中间过程临时文件（前端不可见）
│   └── state/                   # SQLite checkpoints（checkpoints.sqlite）
├── tests/                       # 测试套件
├── run.py                       # 薄 shim → entrypoints/web.py
├── run_wechat.py                # 薄 shim → entrypoints/wechat.py
├── run_wecom.py                 # 薄 shim → entrypoints/wecom.py
├── demo.py                      # 薄 shim → entrypoints/cli.py
├── requirement.txt              # Python 依赖
├── README.md                    # 英文 README
├── README.zh-CN.md              # 本文件（中文）
├── README_ARCHITECTURE.md       # 架构设计文档
├── AGENTS参考.md                # Agent 设计参考
└── deepagent指南.md              # DeepAgents 使用指南
```

## 当前进度

### ✅ 已完成

- [x] 后端 FastAPI 服务框架搭建
- [x] SSE 流式对话（`text/event-stream`），支持 async 异步生成器
- [x] DeepAgents 集成与 Agent 单例懒加载（初始化失败持久化错误状态）
- [x] 前端 Vue 3 + Tauri 2 项目搭建
- [x] 聊天界面与会话管理
- [x] Markdown 渲染与代码高亮（Shiki）
- [x] 文件上传（图片、PDF、Word、Excel、Markdown，20MB 限制）
- [x] 多模态图片输入支持（含模型不支持 vision 时的降级提示）
- [x] HITL 人机协作审批流程（高风险 `execute`；`web_search`/`web_fetch` 默认 allow）
- [x] 前端可配置 API Base URL
- [x] 微信 / 企业微信渠道桥接
- [x] Skills 系统（mineru、excel-xlsx、word-docx、md-to-pdf、daily-report、diagram-design、web-design-engineer、web-video-presentation）
- [x] **思考与最终答案分离**：基于消息结构路由，`thinking_delta` 进折叠区，`delta` 进主答案区
- [x] **产物自动检测**：对话前后对比 `output/` 目录，新增文件通过 `artifact` 事件推送前端
- [x] **命令安全层**（`sandbox/` + `agent_core/execute_policy.py`）：
  - **工作区 Auto**：只读探查 / 只读 git / 已知构建测试 / skills 脚本 → 自动执行
  - **需确认**：`python -c` / `bash -c` / 联网 / 安装 / 未知命令 → 审批一次；批准后绕过软策略
  - **硬拒绝**（批准也不可绕过）：命令替换（`` ` `` / `$()`）、cd 越出 workspace、极危险模式
  - 写路径边界（仅 `output/`、`tmp/`；`skills/` 只读）+ 路径改写 + utf-8/gbk 双解码
  - 子 agent 注入同一 Hooks，修复「批准后 trust 仍为 strict」
  - **不是** OS 级进程沙盒
- [x] 多 LLM Provider 切换（MiMo 默认 / agnes / deepseek 等）
- [x] SSE ping 保活（15 秒间隔）
- [x] TypeScript 完整 SSE 事件类型处理（无 default case）
- [x] Langfuse 可观测性集成（未配置时自动降级）
- [x] **代码目录重构**：根级 `agent_runtime.py` / `ducktools.py` / `html_tools.py` / `time_tools.py` 拆分为 `agent_core/`、`sandbox/`、`tools/`、`entrypoints/`、`artifacts/` 包；统一 `build_agent()` 工厂消除原先三套分歧的 agent 配置
- [x] **SQLite 任务计划持久化**：`DualSqliteSaver`（sync + async 双接口）替换 `BoundedMemorySaver`；thread 状态（messages / todos / files / pending interrupts）跨重启可恢复；HITL resume 跨重启生效；WAL 模式 + busy_timeout + 全局锁保证并发安全
- [x] **多搜索 Provider 失败回退**：`Tavily → Brave → Serper → DuckDuckGo` 链路；API key 留空的 provider 直接跳过不入链路；额度错误触发 1 小时冷却；非额度错误跳过不冷却；DuckDuckGo 兜底
- [x] **子智能体可观测性**：后端开启 `subgraphs=True`，通过 `subagent_start` / `subagent_done` SSE 事件把子智能体任务及嵌套 `tool_call` / `tool_result` 步骤（携带 `subagentId`）流式推送给前端；前端 `FloatingTodoList` 按 `subagentId` 聚合渲染子智能体卡片与嵌套步骤
- [x] **daily-report 日报 Skill** 已加入 Skill 库
- [x] **diagram-design 图表 Skill** 已加入 Skill 库（编辑级独立 HTML/SVG：架构图、流程图、时序图等）

### 🔧 进行中 / 待完善

- [ ] 完整的 Skill 注册与发现机制
- [ ] 更多 Skill 实现（PPT 生成、数据分析、图表生成等）
- [ ] 移动端适配优化
- [ ] 用户认证与权限系统
- [ ] 知识库检索集成
- [ ] 生产环境部署方案（对象存储、远程沙箱等）

### 📋 已知问题与注意事项

- 前端开发时需确保后端 SSE 服务正常运行，否则消息无法显示
- Python 依赖需安装 `fastapi>=0.110`、`uvicorn[standard]>=0.27`、`sse-starlette>=2.0` 以支持 SSE
- SSE 流必须使用 `async def` 异步生成器和 `agent.astream()`，否则会阻塞事件循环
- TypeScript 中需显式处理所有 SSE 事件类型（无 default case）
- **安全路径约束**：Agent 写文件只能落 `output/` 或 `tmp/`，`skills/` 子树完全只读；新增 skill 脚本需放在 `workspace/skills/<name>/scripts/` 下并重启服务才生效
- **HITL 与命令分类**：默认 `EXECUTE_PROFILE=workspace_auto`。常规本地命令自动执行；对高风险 `execute` 的 HITL「批准」仅针对本次调用并绕过软策略。命令替换、cd 越界、极危险命令等硬策略仍拦截。`--always-approve` 跳过全部 ask（仅建议在已隔离环境使用）
- **路径写法**：SKILL.md 里写 `/skills/...`、`D:\skills\...`、`skills/...` 都会被 token 级改写器统一成相对路径；但写产物时必须用 `output/xxx` 相对路径
- **curl 出网**：未批准时仅放行 `api.openai.com`（TTS）；HITL 批准后可访问其它 host；新增默认 TTS 后端可改 `_CURL_ALLOWED_HOSTS`
- **搜索 Provider**：建议至少配置 Tavily / Brave / Serper 中的一个 API key 以获得最佳体验；三者全部留空时链路仅剩 DuckDuckGo 兜底

## 架构文档

详细的架构设计、模块职责、技术选型路线请参考：[README_ARCHITECTURE.md](file:///d:/project/README_ARCHITECTURE.md)

## 开发说明

### SSE 事件格式

前后端通过 SSE 通信，业务 payload 与 CLI `--format streaming-json`（NDJSON）共用 **`schemaVersion: 1`**（见 `agent_core/events.py`）。`start` / `done` 携带 `schemaVersion`；其余事件类型如下：

| 事件类型 | 说明 |
|---------|------|
| `start` | 对话开始，含 `messageId` + `schemaVersion` |
| `delta` | 最终答案文本增量（无 `tool_call_chunks` 的 AIMessageChunk content） |
| `thinking` | 思考开始标记（无文本输出时的心跳指示） |
| `thinking_delta` | 思考过程文本增量（`reasoning_content` 或工具调用轮过渡语，进折叠区） |
| `tool_call` | 模型决定调工具（callId、name、args、可选 `subagentId`），状态 running |
| `tool_result` | 工具执行返回（callId、name、output、可选 `subagentId` / `denied`），状态 completed |
| `subagent_start` | `task()` 子智能体启动（subagentId、subagentType、description） |
| `subagent_done` | `task()` 子智能体结束（subagentId） |
| `tool` | 旧协议兼容（deferred，新代码不产生） |
| `interrupt` | HITL 中断，等待用户审批（groups / toolCalls） |
| `artifact` | 检测到新生成的产物文件（name、path、url、mime、size） |
| `usage` | Token 使用统计（deferred，前端已有 handler） |
| `ping` | 库级 SSE comment 保活（非 JSON 事件；15 秒间隔） |
| `done` | 对话结束（含 `schemaVersion`） |
| `error` | 错误信息 |

**权限与 Hooks**：工具执行前经权限矩阵（`allow`/`ask`/`deny`）与 `hooks/` middleware（主图与子 agent 均注入）。默认工作区 Auto：`write_file`/`edit_file` 自动放行；`execute` 由 `agent_core/execute_policy.py` 分类——auto 跳过 HITL，ask 才弹审批，deny 直接拒绝。Plan 模式拒绝写与 shell。HITL 批准 ask 类 `execute` 后以 `hitl_approved` 运行（绕过软策略，硬拒绝仍生效）。可选在 `workspace/hooks/*.py` 导出 `before_tool` / `after_tool`。

**思考与最终答案分离机制**：基于消息结构路由，不依赖模型输出文本标记。
- `reasoning_content` 或工具调用轮的 content → `thinking_delta`（前端折叠区）
- 无 `tool_call_chunks` 的 AIMessageChunk content → `delta`（前端主答案区）

**子智能体事件语义**：主 agent 调用 `task()` 时，后端开启 `subgraphs=True`，通过 langgraph namespace（`tools:<tid>`）识别子智能体 chunk：
- 首次见到子智能体 chunk → 发射 `subagent_start`（subagentId = base namespace）
- 子智能体内部 `ToolMessage` → 发射 `tool_call` / `tool_result`（携带 `subagentId`）
- 父图 `task()` ToolMessage 收尾 → 发射 `subagent_done`，跳过重复的 tool_call / tool_result

### 前端开发命令

```bash
npm run dev                   # Web 开发
npm run build                 # 构建生产版本
npm run build:web             # Web 模式构建
npm run tauri:dev             # Tauri 桌面开发
npm run tauri:build           # Tauri 桌面构建
npm run tauri:build:android   # Android 构建
npm run tauri:build:ios       # iOS 构建（仅 macOS）
npm run lint                  # ESLint 检查修复
npm run format                # Prettier 格式化
```

## License

待定
