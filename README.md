# 通用任务 Agent 架构 README

本文档记录本项目的长期架构方向，供后续设计、开发、复盘时反复查看。项目目标不是构建一个单一的 PPT Agent，而是构建一个以 DeepAgents 思路为核心的通用任务 Agent Harness：Agent 内核负责理解、规划、调度、状态、人机确认与交付；PPT、联网搜索、知识库检索、数据分析、图片生成、文件导出等能力以可插拔 Skill 或独立服务接入。

## 1. 项目定位

本项目采用“全链路微服务 + Skills”的架构方向，但第一阶段不要求一次性完成完整微服务化。

核心定位：

- General Agent Core 是通用编排内核，不绑定具体业务能力。
- PPT Skill 是第一个垂直技能包，不是 Agent 主体。
- 后续新增报告生成、数据分析、邮件处理、网页搭建等能力时，应复用同一套 Agent Core。
- 架构设计优先遵守 DeepAgents 的组合式思想：通过 `create_deep_agent(...)`、middleware、backend、skills、memory、subagents 等扩展能力，而不是把业务逻辑写死进深继承结构或主提示词。

一句话目标：

```text
构建一个可规划、可调度、可确认、可扩展、可交付文件的通用任务 Agent。
```

## 2. 核心心智模型

项目应区分三层：

```text
Backend Layer
  负责文件、状态、知识库、对象存储、沙箱执行等边界

Middleware Layer
  负责工具注入、系统提示注入、上下文变换、确认拦截、成本控制等横切能力

Graph / Agent Layer
  由 create_deep_agent(...) 或类似装配函数创建 LangGraph runnable / compiled graph
```

Agent 不直接实现“如何制作 PPT”。它只需要知道：

- 什么时候需要制作 PPT；
- 应调用哪个 Skill；
- 给 Skill 什么输入；
- 如何追踪 Skill 状态；
- 什么时候需要用户确认；
- 如何检查与交付输出。

## 3. 总体架构

```text
用户入口层
  ↓
Agent Orchestrator 通用编排内核
  ↓
Planner / Task Manager 任务规划层
  ↓
Human-in-the-loop 决策确认层
  ↓
Skill Router 技能路由层
  ↓
Skills 微服务层
  ├── PPT Skill
  ├── Web Search Skill
  ├── Knowledge Retrieval Skill
  ├── Data Analysis Skill
  ├── Image / Chart Skill
  └── File Export Skill
  ↓
Backend / Sandbox / File System 执行与文件层
  ↓
Artifact Delivery 结果交付层
```

推荐最终形态：

```text
General Agent Core
  ├── Planner
  ├── Skill Router
  ├── HITL Manager
  ├── Memory Manager
  ├── Context Manager
  ├── File Manager
  └── Execution Manager

Skill Layer
  ├── PPT Skill
  ├── Search Skill
  ├── KB Skill
  ├── Chart Skill
  ├── Review Skill
  └── Export Skill

Infrastructure Layer
  ├── Backend Protocol
  ├── Sandbox Protocol
  ├── Object Storage
  ├── Vector DB
  ├── Queue
  └── Observability
```

## 4. 关键模块职责

### 4.1 Agent Orchestrator

Agent Orchestrator 是通用编排内核，负责：

- 理解用户需求；
- 判断任务类型；
- 拆解任务步骤；
- 选择和调用 Skill；
- 管理上下文和长期记忆；
- 插入人机确认节点；
- 追踪任务状态；
- 汇总结果并交付文件。

建议抽象为类似下面的装配函数：

```python
create_general_agent(
    *,
    model,
    tools,
    skills,
    backend,
    memory=None,
    subagents=None,
    interrupt_on=None,
    middleware=None,
)
```

实现时优先沿用 DeepAgents 的 `create_deep_agent(...)` 思路，把能力作为参数组合进去。

### 4.2 Planner / Task Manager

Planner 负责把用户自然语言需求拆成结构化任务。任务状态至少包含：

```text
pending
running
waiting_user
completed
failed
cancelled
```

一个 PPT 任务的典型计划：

```text
确认需求
→ 联网搜索
→ 检索知识库
→ 生成大纲
→ 用户确认大纲
→ 生成每页内容
→ 生成视觉风格方案
→ 用户确认风格
→ 制作 PPT 文件
→ 质量审查
→ 用户确认终稿
→ 交付文件
```

任务计划建议持久化到数据库或后端状态中，避免长任务中断后无法恢复。

### 4.3 Human-in-the-loop Manager

HITL 是通用机制，不应写成 PPT 专属逻辑。

常见确认点：

- 是否联网搜索；
- 是否使用用户知识库；
- 是否调用高成本模型或外部 API；
- 是否确认任务大纲；
- 是否确认视觉风格；
- 是否执行沙箱代码；
- 是否导出最终文件；
- 是否向外部系统发送结果。

示例配置：

```json
{
  "interrupt_on": {
    "before_expensive_search": true,
    "before_external_api_call": true,
    "before_outline_generation": true,
    "before_file_export": true
  }
}
```

Skill 可以声明自己的确认点：

```json
{
  "skill": "ppt_builder",
  "human_checkpoints": [
    "confirm_outline",
    "confirm_visual_style",
    "confirm_final_export"
  ]
}
```

### 4.4 Skill Router

Skill Router 负责根据任务目标选择 Skill，并把上下文转换成 Skill 需要的输入格式。

它不应依赖硬编码业务分支，而应读取 Skill Registry 中的能力描述、输入输出 Schema、成本、耗时、权限和确认要求。

用户请求示例：

```text
帮我做一份关于新能源行业的投资分析 PPT。
```

可能路由为：

```text
web_search_skill
→ kb_retrieval_skill
→ data_analysis_skill
→ outline_skill
→ ppt_builder_skill
→ review_skill
→ export_skill
```

### 4.5 Skill Registry

Skill Registry 是技能市场，负责注册、发现和描述 Skill。

每个 Skill 应至少声明：

```json
{
  "name": "ppt_builder",
  "version": "1.0.0",
  "description": "根据大纲、内容、风格和素材生成 PowerPoint 文件",
  "capabilities": [
    "outline_to_deck",
    "theme_design",
    "chart_slide_generation",
    "pptx_export"
  ],
  "input_schema": {},
  "output_schema": {},
  "cost_level": "high",
  "latency_level": "medium",
  "requires_sandbox": true,
  "requires_human_approval": [
    "outline",
    "style",
    "final"
  ]
}
```

Skill Registry 是实现“Agent Core 与具体能力解耦”的关键。

### 4.6 Skills 微服务层

Skill 可以先以本地模块实现，后续再迁移成独立 HTTP 服务或异步 Worker。

推荐 Skill 类型：

| Skill | 职责 | 通用性 |
| --- | --- | --- |
| PPT Skill | 生成和修改 PPT 文件 | 垂直技能 |
| Web Search Skill | 联网搜索、资料整理、引用记录 | 通用 |
| Knowledge Retrieval Skill | 检索用户私有知识库 | 通用 |
| Data Analysis Skill | 数据清洗、统计分析、图表计算 | 通用 |
| Chart / Image Skill | 生成图表、图片、视觉素材 | 半通用 |
| Review Skill | 内容、事实、格式、版式审查 | 半通用 |
| Export Skill | 导出 PPTX、PDF、图片预览、压缩包 | 半通用 |

PPT Skill 内部可以继续拆分：

```text
PPT Skill
  ├── outline_to_slides
  ├── slide_copywriter
  ├── layout_designer
  ├── chart_generator
  ├── asset_collector
  ├── pptx_renderer
  ├── visual_reviewer
  └── export_checker
```

这些内部细节对 Agent Core 保持透明。

### 4.7 Backend / Sandbox / File System

Backend 负责存储和执行边界。建议参考 DeepAgents 的 `BackendProtocol` / `SandboxBackendProtocol` 思路。

推荐后端能力：

```text
Backend
  ├── State Backend：短期任务状态
  ├── File Backend：用户文件、中间文件、最终文件
  ├── Knowledge Backend：向量库 / 文档库
  ├── Sandbox Backend：运行代码、生成图表、渲染文件
  └── Artifact Backend：管理最终交付物
```

原则：

- PPT Skill 不应直接依赖本地磁盘路径，应依赖统一 File API。
- 需要执行代码、渲染 PPT、调用 LibreOffice 或 Playwright 时，应进入沙箱。
- `virtual_mode` 和路径检查不是安全边界；不可信代码必须运行在真实沙箱中。
- 本地开发可以使用 `FilesystemBackend + LocalSandbox`，生产环境应使用对象存储和远程沙箱。

## 5. Memory 与 Skills 的边界

Memory 和 Skills 要严格区分：

```text
Memory
  用户偏好、项目背景、品牌规范、历史任务经验、长期上下文

Skills
  可复用流程、能力说明、输入输出协议、工具调用规范、示例
```

不要把 PPT 制作流程写进 Agent 主提示词。它应该放在 PPT Skill 中。

不要把用户偏好、品牌色、历史项目约定写进 Skill。它们应该进入 Memory。

## 6. Middleware 设计建议

适合做成 middleware 的能力：

```text
RequirementClarificationMiddleware
SkillSelectionMiddleware
HumanApprovalMiddleware
FileContextMiddleware
CitationMiddleware
QualityCheckMiddleware
CostControlMiddleware
ObservabilityMiddleware
```

使用原则：

- 每次模型调用前后都要运行的横切逻辑，用 middleware。
- 需要模型主动调用的业务动作，用 tool 或 skill。
- middleware 职责要窄，避免把慢网络调用塞进模型调用路径。
- 增加同步逻辑时，注意保留 async 变体。

## 7. PPT 任务标准流程

示例需求：

```text
帮我做一份 12 页的 AI Agent 行业分析 PPT，面向投资人，风格要像咨询公司报告。
```

标准流程：

```text
1. 需求理解
2. 信息补全和用户确认
3. 创建任务计划
4. 联网搜索和知识库检索
5. 生成核心观点
6. 生成 PPT 大纲
7. 用户确认大纲
8. 生成每页内容
9. 生成视觉风格方案
10. 用户确认风格
11. 调用 PPT Skill 生成文件
12. 调用 Review Skill 审查
13. 修复问题
14. 用户确认终稿
15. 交付 PPTX / PDF / 预览图 / 质量报告
```

PPT Skill 输入示例：

```json
{
  "topic": "AI Agent 行业分析",
  "audience": "投资人",
  "slide_count": 12,
  "style": {
    "type": "consulting",
    "tone": "professional",
    "layout": "data-heavy",
    "visual_density": "medium-high"
  },
  "outline": [],
  "research": [],
  "brand_assets": [],
  "output_format": "pptx"
}
```

PPT Skill 输出示例：

```json
{
  "pptx_path": "/artifacts/ai_agent_industry_analysis.pptx",
  "pdf_path": "/artifacts/ai_agent_industry_analysis.pdf",
  "preview_images": [
    "/artifacts/preview/page_1.png",
    "/artifacts/preview/page_2.png"
  ],
  "quality_report_path": "/artifacts/quality_report.md"
}
```

## 8. 服务拆分建议

| 服务 | 作用 | 是否通用 |
| --- | --- | --- |
| Agent Orchestrator | 任务理解、规划、调度、上下文管理 | 是 |
| Skill Registry | 注册、发现、描述 Skill 能力 | 是 |
| Human Interaction Service | 管理确认、暂停、恢复、用户反馈 | 是 |
| Memory Service | 用户偏好、项目记忆、品牌规范 | 是 |
| Knowledge Retrieval Service | 私有知识库检索 | 是 |
| Web Search Service | 联网搜索与资料整理 | 是 |
| File Service | 文件读写、版本管理、交付物管理 | 是 |
| Sandbox Service | 安全执行代码、渲染文件 | 是 |
| PPT Skill Service | 生成 PPT | 否，垂直技能 |
| Review Skill Service | 检查质量 | 半通用 |
| Export Service | PPTX / PDF / 图片导出 | 半通用 |

第一阶段可以是单体内的模块化 Skill；第二阶段再拆成服务。

## 9. 推荐 MVP 路线

### MVP 1：单 Orchestrator + 本地 Skills

先跑通端到端流程：

```text
用户需求
→ 需求确认
→ 搜索 / 检索
→ 大纲生成
→ 大纲确认
→ PPT 生成
→ 质量检查
→ 文件交付
```

实现形态：

```text
Agent Orchestrator
  ├── local web_search_tool
  ├── local kb_retrieval_tool
  ├── local ppt_builder_skill
  ├── local file_backend
  └── human_approval
```

目标是验证协议、流程和用户体验。

### MVP 2：Skill Registry + PPT Skill 独立服务

拆出 PPT Skill：

```text
Agent Orchestrator
  ↓
Skill Registry
  ↓
ppt-skill-service
```

目标是验证 Agent Core 与垂直能力解耦。

### MVP 3：多 Skill 微服务 + 异步任务队列

引入：

```text
PostgreSQL
Redis / RabbitMQ / Kafka
Object Storage / MinIO / S3
Vector DB / pgvector / Qdrant
Remote Sandbox
Tracing / Metrics / Logs
```

目标是支持复杂任务、长任务、多人并发和企业化部署。

## 10. 技术选型方向

可选技术栈：

```text
Agent 编排：
- DeepAgents / LangGraph / LangChain
- 自研 Orchestrator 状态机

Skill 服务：
- FastAPI
- Celery / Dramatiq / Temporal

任务状态：
- PostgreSQL

异步队列：
- Redis / RabbitMQ / Kafka

文件存储：
- S3 / MinIO / OSS

知识库：
- PostgreSQL + pgvector
- Qdrant / Milvus

沙箱：
- Docker Sandbox
- Firecracker
- Daytona / Modal / Runloop 等远程运行环境

PPT 生成：
- python-pptx
- pptxgenjs
- LibreOffice headless
- HTML/CSS → screenshot → slide
```

选择原则：

- 先验证端到端流程，再引入重型基础设施。
- Agent Core 不依赖具体 PPT 渲染库。
- Skill 协议要稳定，内部实现可以迭代。
- 长任务优先异步化。

## 11. 质量审查标准

PPT 交付前至少检查：

内容质量：

- 是否符合用户目标和受众；
- 是否跑题；
- 是否有逻辑断层；
- 是否页面重复；
- 是否关键结论明确。

事实质量：

- 关键数据是否有来源；
- 是否使用过时信息；
- 是否区分事实、推断和建议；
- 是否记录引用。

版式质量：

- 标题层级是否一致；
- 字体、颜色、间距是否统一；
- 图表是否清晰；
- 页面留白是否合理；
- 导出文件是否可打开。

交付质量：

- 是否生成 PPTX；
- 是否生成 PDF 或预览图；
- 是否提供质量报告；
- 是否记录用户确认点和修改历史。

## 12. 安全与工程约束

必须遵守：

- 不在代码中硬编码密钥；
- 不记录用户敏感内容到非必要日志；
- 不用 `eval`、`exec`、`pickle` 处理不可信输入；
- 不把路径检查当成沙箱；
- 不让主 Agent 服务直接执行不可信代码；
- 外部 API、高成本任务和文件导出应有确认点或策略控制；
- 公共 API 保持类型标注和兼容性；
- 新增能力优先通过 Skill、tool、middleware、backend 扩展。

## 13. 后续开发检查清单

开发新能力前，先回答：

- 这是通用编排能力，还是垂直 Skill 能力？
- 应该放在 Memory、Skill、Tool、Middleware、Backend 还是 SubAgent？
- 是否需要人机确认？
- 是否会产生长任务？
- 是否需要沙箱？
- 输入输出 Schema 是否稳定？
- 是否需要记录引用、成本、耗时和 Trace？
- 是否会影响 `create_deep_agent(...)` 的默认行为或公共 API？

新增 Skill 前，至少补齐：

- `name`
- `version`
- `description`
- `capabilities`
- `input_schema`
- `output_schema`
- `cost_level`
- `latency_level`
- `requires_sandbox`
- `requires_human_approval`
- 错误码和重试策略
- 示例输入输出

## 14. 当前架构决策

当前建议采用：

```text
短期：
  单体 Orchestrator + 本地可插拔 Skill 协议

中期：
  Skill Registry + PPT Skill 独立服务

长期：
  多 Skill 微服务 + 异步队列 + 对象存储 + 沙箱 + 可观测性
```

最重要的长期约束：

```text
扩展运行环境和 Skill 能力，不污染 Agent Core。
```

