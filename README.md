# DeepAgent 通用任务 Agent

一个基于 DeepAgents/LangGraph 构建的可扩展通用任务 Agent 系统，支持 Web 界面、桌面应用和移动端，具备 SSE 流式对话、人机协作（HITL）、文件上传、多渠道接入（微信/企业微信）等能力。

## 项目介绍

本项目采用"全链路微服务 + Skills"架构，核心是一个通用 Agent 编排内核，不绑定具体业务能力。PPT生成、联网搜索、知识库检索、数据分析、文件处理等能力以可插拔 Skill 形式接入。

### 核心特性

- 🤖 **通用 Agent 内核**：基于 DeepAgents，支持任务规划、工具调度、状态管理
- 🔌 **可插拔 Skills 系统**：支持文档解析、Excel/Word处理、网页设计、视频演示等技能扩展
- 🌊 **SSE 流式响应**：实时推送对话内容、工具调用状态、思考过程
- 👤 **人机协作（HITL）**：关键操作前支持用户审批/拒绝
- 📁 **多模态支持**：图片、文档（PDF/Word/Excel/Markdown）上传与解析
- 💬 **多渠道接入**：微信、企业微信渠道桥接
- 🖥️ **跨平台前端**：Web + 桌面（Tauri 2）+ 移动端，基于 Vue 3 + TypeScript
- 🔧 **可配置 API 地址**：前端设置面板可动态配置后端服务地址

## 技术栈

### 后端
- Python 3.10+
- FastAPI + uvicorn + sse-starlette（SSE 服务）
- DeepAgents + LangGraph（Agent 编排）
- LangChain（模型与工具集成）
- 可选：Langfuse（可观测性）

### 前端
- Vue 3.5 + TypeScript 5.6
- Tauri 2（跨平台桌面/移动端）
- Vite 5.4（构建工具）
- Tailwind CSS 3.4（样式）
- Pinia 2.3（状态管理）
- Vue Router 4.5（路由）

## 快速开始

### 环境准备

1. Python 3.10+
2. Node.js 18+
3. npm 或 pnpm

### 后端启动

1. 安装 Python 依赖：

```bash
pip install -r requirement.txt
```

2. 配置环境变量（可选，创建 `.env` 文件）：

```env
# LLM 配置（根据实际使用的模型配置）
OPENAI_API_KEY=your-api-key
OPENAI_BASE_URL=https://api.openai.com/v1

# 服务配置
PORT=8000
HOST=0.0.0.0
HITL_ENABLED=true

# 可选：Langfuse 配置
# LANGFUSE_PUBLIC_KEY=...
# LANGFUSE_SECRET_KEY=...
# LANGFUSE_HOST=...
```

3. 启动后端服务：

```bash
python run.py
```

服务默认运行在 `http://localhost:8000`

**后端 API 端点：**
- `GET /health` - 健康检查
- `POST /upload` - 文件上传（图片/文档）
- `POST /chat` - 发起/继续对话（返回 SSE 流）
- `POST /chat/resume` - HITL 中断后提交审批决定
- `GET /uploads/<filename>` - 静态文件访问

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

## 项目结构

```
d:\project
├── agent-frontend/          # Tauri + Vue 前端
│   ├── src/
│   │   ├── api/             # API 客户端与 SSE 处理
│   │   ├── components/      # Vue 组件（聊天面板、布局、主题等）
│   │   ├── composables/     # 组合式函数
│   │   ├── router/          # 路由配置
│   │   ├── stores/          # Pinia 状态管理（会话、设置）
│   │   ├── styles/          # 全局样式
│   │   ├── types/           # TypeScript 类型定义
│   │   └── views/           # 页面视图
│   ├── src-tauri/           # Tauri Rust 后端
│   └── scripts/             # 工具脚本
├── channels/                # 多渠道桥接
│   ├── wechat/              # 微信渠道
│   └── wecom/               # 企业微信渠道
├── workspace/               # 工作目录
│   ├── skills/              # Skill 定义与实现
│   │   ├── document-parser/ # 文档解析 Skill
│   │   ├── excel-xlsx/      # Excel 处理 Skill
│   │   ├── word-docx/       # Word 处理 Skill
│   │   ├── web-design-engineer/ # 网页设计 Skill
│   │   └── web-video-presentation/ # 视频演示 Skill
│   ├── uploads/             # 用户上传文件存储
│   ├── output/              # 生成文件输出
│   └── tmp/                 # 临时文件
├── agent_runtime.py         # Agent 运行时核心（LLM、后端、提示词、工具）
├── run.py                   # FastAPI Web 服务入口
├── run_wechat.py            # 微信渠道入口
├── run_wecom.py             # 企业微信渠道入口
├── ducktools.py             # DuckDuckGo 搜索工具
├── html_tools.py            # HTML 渲染工具
├── time_tools.py            # 时间工具
├── requirement.txt          # Python 依赖
├── README_ARCHITECTURE.md   # 架构设计文档（详细架构说明）
└── .gitignore               # Git 忽略配置
```

## 当前进度

### ✅ 已完成

- [x] 后端 FastAPI 服务框架搭建
- [x] SSE 流式对话（text/event-stream），支持 async 异步生成器
- [x] DeepAgents 集成与 Agent 单例懒加载
- [x] 前端 Vue 3 + Tauri 2 项目搭建
- [x] 聊天界面与会话管理
- [x] Markdown 渲染与代码高亮（Shiki）
- [x] 文件上传（图片、PDF、Word、Excel、Markdown）
- [x] 多模态图片输入支持
- [x] HITL 人机协作审批流程（web_search、execute 工具）
- [x] 前端可配置 API Base URL
- [x] 微信/企业微信渠道桥接
- [x] Skills 系统基础框架（文档解析、Excel、Word、网页设计、视频演示）
- [x] SSRF 防护（内网地址访问限制）
- [x] SSE ping 保活（15秒间隔）
- [x] TypeScript 完整 SSE 事件类型处理（thinking、ping 等）

### 🔧 进行中 / 待完善

- [ ] 完整的 Skill 注册与发现机制
- [ ] 任务计划持久化与断点续传
- [ ] 更多 Skill 实现（PPT生成、数据分析、图表生成等）
- [ ] 移动端适配优化
- [ ] 用户认证与权限系统
- [ ] 知识库检索集成
- [ ] 生产环境部署方案（对象存储、远程沙箱等）

### 📋 已知问题与注意事项

- 前端开发时需确保后端 SSE 服务正常运行，否则消息无法显示
- Python 依赖需安装 `fastapi>=0.110`、`uvicorn[standard]>=0.27`、`sse-starlette>=2.0` 以支持 SSE
- SSE 流必须使用 `async def` 异步生成器和 `agent.astream()`，否则会阻塞事件循环
- TypeScript 中需显式处理所有 SSE 事件类型（无 default case）

## 架构文档

详细的架构设计、模块职责、技术选型路线请参考：[README_ARCHITECTURE.md](file:///d:/project/README_ARCHITECTURE.md)

## 开发说明

### SSE 事件格式

前后端通过 SSE 通信，事件类型包括：

| 事件类型 | 说明 |
|---------|------|
| `start` | 对话开始，包含 messageId |
| `delta` | 文本增量内容 |
| `thinking` | Agent 思考中（无文本输出时） |
| `tool` | 工具调用完成（名称、参数、预览） |
| `interrupt` | HITL 中断，等待用户审批 |
| `usage` | Token 使用统计 |
| `ping` | 心跳保活 |
| `done` | 对话结束 |
| `error` | 错误信息 |

### 前端开发命令

```bash
npm run dev          # Web 开发
npm run build        # 构建生产版本
npm run build:web    # Web 模式构建
npm run tauri:dev    # Tauri 桌面开发
npm run tauri:build  # Tauri 桌面构建
npm run lint         # ESLint 检查修复
npm run format       # Prettier 格式化
```

## License

待定
