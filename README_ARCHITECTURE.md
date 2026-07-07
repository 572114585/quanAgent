# 通用任务 Agent 架构 README

本文档记录本项目的长期架构方向，供后续设计、开发、复盘时反复查看。项目目标不是构建一个单一的 PPT Agent，而是构建一个以 DeepAgents 思路为核心的通用任务 Agent Harness：Agent 内核负责理解、规划、调度、状态、人机确认与交付；文档生成（PDF）、联网搜索、知识库检索、数据分析、可视化图表、文件导出等能力以可插拔 Skill 或独立服务接入。

## 1. 项目定位

本项目采用"全链路微服务 + Skills"的架构方向，但第一阶段不要求一次性完成完整微服务化。

核心定位：

- General Agent Core 是通用编排内核，不绑定具体业务能力。
- **文档智能生成（PDF）是第一个核心垂直能力**，不是 Agent 主体。
- 后续新增报告生成、数据分析、邮件处理、网页搭建等能力时，应复用同一套 Agent Core。
- 架构设计优先遵守 DeepAgents 的组合式思想：通过 `create_deep_agent(...)`、middleware、backend、skills、memory、subagents 等扩展能力，而不是把业务逻辑写死进深继承结构或主提示词。

一句话目标：

```text
构建一个可规划、可调度、可确认、可扩展、可交付文件的通用任务 Agent，
第一个垂直目标是：把各类收集来的信息整合成结构化 PDF 文档
（产品介绍、技术调研方案、新闻日报、数据分析等主题）。
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

Agent 不直接实现"如何写一篇技术调研"。它只需要知道：

- 什么时候需要生成文档；
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
  ├── Document Builder Skill（文档生成，核心垂直能力）
  │     ├── Research Collector（内容检索，深度调控）
  │     ├── Outline Planner（大纲规划）
  │     ├── Section Writer（逐节撰写子智能体）
  │     ├── Auto Reviewer（自动审查）
  │     ├── Rework Planner（返工修改）
  │     └── HTML Renderer（HTML 制作 + 转 PDF）
  ├── Web Search Skill
  ├── Knowledge Retrieval Skill
  ├── Data Analysis Skill
  ├── Chart / Image Skill
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
  ├── Document Builder Skill（核心）
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

一个文档生成任务的典型计划：

```text
确认需求与文档类型
→ 内容检索（深度调控质量/数量/长度）
→ 用户确认检索方向
→ 生成大纲（按文档类型模板）
→ 用户确认大纲
→ 逐节撰写内容（子智能体，可并行或顺序，不能一口气做几页）
→ 自动 Review（对照需求和大纲）
→ 制定修改计划（优先局部修改）
→ 返工修改
→ 制作每页 HTML
→ 审查 HTML
→ 返工 HTML
→ 完成 HTML → 转 PDF
→ 用户确认终稿
→ 交付 PDF
```

任务计划建议持久化到数据库或后端状态中，避免长任务中断后无法恢复。

### 4.3 Human-in-the-loop Manager

HITL 是通用机制，不应写成文档生成专属逻辑。

常见确认点：

- 是否联网搜索；
- 是否使用用户知识库；
- 是否调用高成本模型或外部 API；
- 是否确认检索方向；
- 是否确认大纲；
- 是否确认终稿；
- 是否执行沙箱代码；
- 是否导出最终文件。

示例配置：

```json
{
  "interrupt_on": {
    "before_expensive_search": true,
    "before_outline_generation": true,
    "before_file_export": true
  }
}
```

Skill 可以声明自己的确认点：

```json
{
  "skill": "document_builder",
  "human_checkpoints": [
    "confirm_research_direction",
    "confirm_outline",
    "confirm_final_export"
  ]
}
```

### 4.4 Skill Router

Skill Router 负责根据任务目标选择 Skill，并把上下文转换成 Skill 需要的输入格式。

它不应依赖硬编码业务分支，而应读取 Skill Registry 中的能力描述、输入输出 Schema、成本、耗时、权限和确认要求。

用户请求示例：

```text
帮我做一份关于新能源行业的技术调研报告 PDF。
```

可能路由为：

```text
web_search_skill（深度调控检索）
→ kb_retrieval_skill（私有知识库补充）
→ document_builder_skill（大纲 → 逐节撰写 → Review → 返工 → HTML → PDF）
→ export_skill（最终 PDF 交付）
```

### 4.5 Skill Registry

Skill Registry 是技能市场，负责注册、发现和描述 Skill。

每个 Skill 应至少声明：

```json
{
  "name": "document_builder",
  "version": "1.0.0",
  "description": "根据检索资料、文档类型和大纲，逐节生成内容，自动审查返工，最终输出 HTML 并转 PDF",
  "capabilities": [
    "research_collection",
    "outline_planning",
    "section_writing",
    "auto_review",
    "rework_planning",
    "html_rendering",
    "pdf_export"
  ],
  "input_schema": {},
  "output_schema": {},
  "cost_level": "high",
  "latency_level": "high",
  "requires_sandbox": true,
  "requires_human_approval": [
    "outline",
    "final"
  ]
}
```

Skill Registry 是实现"Agent Core 与具体能力解耦"的关键。

### 4.6 Skills 微服务层

Skill 可以先以本地模块实现，后续再迁移成独立 HTTP 服务或异步 Worker。

推荐 Skill 类型：

| Skill | 职责 | 通用性 |
| --- | --- | --- |
| Document Builder Skill | 信息整合、大纲规划、逐节撰写、审查返工、HTML→PDF | 垂直技能（核心） |
| Web Search Skill | 联网搜索、资料整理、引用记录、深度调控 | 通用 |
| Knowledge Retrieval Skill | 检索用户私有知识库 | 通用 |
| Data Analysis Skill | 数据清洗、统计分析、图表计算 | 通用 |
| Chart / Image Skill | 生成图表、图片、视觉素材 | 半通用 |
| Review Skill | 内容、事实、格式、版式审查 | 半通用 |
| Export Skill | 导出 PDF、图片预览、压缩包 | 半通用 |

Document Builder Skill 内部拆分（对 Agent Core 保持透明）：

```text
Document Builder Skill
  ├── Research Collector      内容检索，按需调控质量/数量/长度
  ├── Outline Planner         按文档类型生成结构化大纲
  ├── Section Writer          逐节撰写子智能体（可见全局进度）
  ├── Auto Reviewer           对照需求+大纲自动审查
  ├── Rework Planner          制定局部修改计划
  ├── HTML Renderer           每页内容(md) → HTML 制作
  └── PDF Export              HTML → PDF（复用 md-to-pdf 的 render_pdf.py）
```

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

- Document Builder Skill 不应直接依赖本地磁盘路径，应依赖统一 File API。
- 需要执行代码、渲染 PDF、调用 Playwright 时，应进入沙箱。
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

不要把文档撰写流程写进 Agent 主提示词。它应该放在 Document Builder Skill 中。

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

## 7. 文档生成标准流程

> 这是本项目的核心垂直流程，替代原 PPT 流程。

示例需求：

```text
帮我做一份 12 页的 AI Agent 行业技术调研报告 PDF，面向技术决策者，需要覆盖技术原理、主流框架对比、落地场景。
```

### 7.1 总流程

```text
1. 需求理解（确定文档类型：产品介绍 / 技术调研 / 新闻日报 / 数据分析 / ...）
2. 内容检索（深度调控：根据所需内容深度，调控检索质量、数量、内容长度）
3. 用户确认检索方向
4. 整合内容 → 生成大纲（按文档类型模板，整体撰写规划）
5. 用户确认大纲
6. 逐节撰写内容（子智能体，可并行或顺序，不能一口气做几页）
7. 自动 Review（从用户需求出发，看是否满足，与大纲是否吻合）
8. 制定修改计划（不吻合时，优先局部修改）
9. 返工修改
10. 写每页 HTML 展示的内容及呈现方式（md 描述）
11. 制作每页 HTML
12. 审查 HTML
13. 返工 HTML
14. 完成 HTML 制作 → 转 PDF
15. 用户确认终稿
16. 交付 PDF
```

### 7.2 关键约束

#### 7.2.1 内容检索的深度调控

检索不能"一把搜完"。应根据文档类型和所需内容深度，动态调控：

```text
质量调控：
  - 技术调研：优先权威来源（官方文档、论文、技术博客），过滤营销内容
  - 新闻日报：优先时效性来源（近 7 天），优先一手报道
  - 数据分析：优先带数据的来源（统计报告、财报、行业数据）
  - 产品介绍：优先官方资料、用户评价、竞品对比

数量调控：
  - 深度报告：每主题 5-10 条来源，交叉验证
  - 快报/日报：每主题 2-3 条来源，快速聚合
  - 数据分析：每指标 3+ 独立来源验证

内容长度调控：
  - 概述类章节：检索摘要级内容（200-500 字/条）
  - 深度分析章节：检索全文级内容（保留完整论证）
  - 数据展示章节：检索结构化数据（表格、数字）
```

#### 7.2.2 逐节撰写约束

**不能一口气做几页**。撰写必须分节/分页进行，每节由子智能体独立完成：

```text
允许的模式：
  - 顺序模式：第 1 节完成 → 第 2 节开始 → ...（强一致性，慢）
  - 并行模式：多节同时撰写，但每节独立子智能体（快，需事后统一）

禁止的模式：
  - 一次调用让模型直接产出全部内容
  - 跳过大纲直接写正文
```

#### 7.2.3 子智能体全局进度感知

撰写子智能体在写每一节时，必须能看到整个文档的完成进度：

```text
子智能体上下文包含：
  - 文档类型与用户原始需求
  - 完整大纲（所有节的标题 + 摘要）
  - 已完成节的内容摘要（前文回顾）
  - 当前要写的节在大纲中的位置
  - 后续待写节的标题（前瞻，避免重复）

目的：
  - 前后一致性：避免概念重复定义、数据前后矛盾
  - 连贯性：章节间有逻辑过渡
  - 引用一致性：同一数据源在不同节引用一致
```

#### 7.2.4 自动 Review 机制

Review 不是可选步骤，是闭环的必要环节：

```text
Review 维度：
  1. 需求满足度：用户要的东西都覆盖了吗？
  2. 大纲吻合度：实际内容与规划大纲一致吗？
  3. 事实准确性：关键数据有来源吗？过时了吗？
  4. 连贯性：章节间逻辑通顺吗？有矛盾吗？
  5. 完整性：有没有空节、占位符、TODO 残留？

Review 输出：
  - 通过 → 进入 HTML 制作
  - 不通过 → 修改计划（标注每条问题的位置 + 修改建议）

修改计划原则：
  - 优先局部修改（只改有问题的节，不重写全文）
  - 按严重程度排序（事实错误 > 需求缺失 > 连贯问题 > 表述问题）
  - 局部修改后重新 Review 受影响节段
```

### 7.3 Document Builder Skill 输入示例

```json
{
  "doc_type": "tech_research",
  "topic": "AI Agent 行业技术调研",
  "audience": "技术决策者",
  "target_pages": 12,
  "style": {
    "tone": "professional",
    "density": "medium-high",
    "citation_required": true
  },
  "research": [],
  "outline": [],
  "output_format": "pdf"
}
```

### 7.4 Document Builder Skill 输出示例

```json
{
  "pdf_path": "/artifacts/ai_agent_tech_research.pdf",
  "html_dir": "/artifacts/html/",
  "preview_images": [
    "/artifacts/preview/page_1.png",
    "/artifacts/preview/page_2.png"
  ],
  "quality_report_path": "/artifacts/quality_report.md",
  "review_log_path": "/artifacts/review_log.md"
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
| Web Search Service | 联网搜索与资料整理（含深度调控） | 是 |
| File Service | 文件读写、版本管理、交付物管理 | 是 |
| Sandbox Service | 安全执行代码、渲染文件 | 是 |
| Document Builder Service | 文档生成（核心垂直能力） | 否，垂直技能 |
| Review Skill Service | 检查质量 | 半通用 |
| Export Service | PDF / 图片导出 | 半通用 |

第一阶段可以是单体内的模块化 Skill；第二阶段再拆成服务。

## 9. 推荐 MVP 路线（从终态目标反推）

### 终态目标

```text
用户说"帮我做一份 XX 主题的 YY 类型 PDF"
→ Agent 自动检索资料（深度调控）
→ 生成大纲 → 用户确认
→ 逐节撰写（子智能体，全局进度感知，连贯一致）
→ 自动 Review → 局部返工
→ 每页 HTML 制作 → 审查 → 返工
→ HTML 转 PDF → 交付
```

### 反推能力清单

从终态倒推，需要以下能力：

| # | 能力 | 当前状态 | 所属阶段 |
| --- | --- | --- | --- |
| 1 | Agent Core（编排+HITL+SSE+沙箱） | ✅ 已完成 | MVP 1 |
| 2 | 基础检索（web_search + kb_search） | ✅ 已完成 | MVP 1 |
| 3 | research subagent（检索委托） | ✅ 已完成 | MVP 1 |
| 4 | md-to-pdf（HTML→PDF 渲染） | ✅ 已完成 | MVP 1 |
| 5 | web-viz-libraries（图表/可视化库） | ✅ 已完成 | MVP 1 |
| 6 | 产物检测与交付 | ✅ 已完成 | MVP 1 |
| 7 | **检索深度调控**（质量/数量/长度参数化） | ✅ 已完成（research-strategies skill） | MVP 2 |
| 8 | **大纲规划器**（按文档类型生成结构化大纲） | ✅ 已完成（outline-planner skill） | MVP 2 |
| 9 | **逐节撰写子智能体**（全局进度感知） | ✅ 已完成（section-writer skill + 子 agent） | MVP 2 |
| 10 | **自动 Review**（对照需求+大纲） | ✅ 已完成（auto-review skill） | MVP 2 |
| 11 | **局部返工机制**（修改计划+执行） | ✅ 已完成（auto-review skill Step2） | MVP 2 |
| 12 | **HTML 制作工作流**（每页 md→HTML） | ✅ 已完成（md-to-pdf skill） | MVP 2 |
| 13 | **文档类型模板**（产品介绍/技术调研/新闻日报/数据分析） | ✅ 已完成（outline-planner/references/doc-type-templates.md） | MVP 2 |
| 14 | **端到端编排**（整合 5 个 Phase 的 document-builder skill） | ✅ 已完成（document-builder skill） | MVP 2 |
| 15 | Skill Registry（正式 Schema 声明） | ❌ 待实现 | MVP 3 |
| 16 | Skill 独立服务化 | ❌ 待实现 | MVP 3 |
| 17 | 多 Skill 微服务 + 异步队列 | ❌ 待实现 | MVP 4 |

### MVP 1：单 Orchestrator + 本地 Skills（已完成）

已跑通端到端基础流程：

```text
Agent Core
  ├── local web_search_tool
  ├── local kb_retrieval_tool
  ├── local md-to-pdf skill（HTML → PDF）
  ├── local web-viz-libraries skill（图表/3D/动画库）
  ├── local file_backend
  ├── local sandbox
  └── human_approval
```

已验证：协议、流程、SSE 流式、HITL、产物交付。

### MVP 2：文档生成核心工作流（已完成）

**已完成阶段。** 目标是让 Agent 能完成"信息整合 → PDF 输出"的完整闭环。已通过 document-builder skill 整合 5 个 Phase 实现端到端编排。

```text
Agent Core
  ├── Enhanced Search（深度调控：质量/数量/长度）
  ├── Outline Planner（按文档类型生成大纲）
  ├── Section Writer Subagent（逐节撰写，全局进度感知）
  ├── Auto Reviewer（对照需求+大纲审查）
  ├── Rework Planner（局部修改计划）
  ├── HTML Renderer（每页 md → HTML 制作）
  └── PDF Export（复用 render_pdf.py）
```

MVP 2 的拆解（按依赖顺序）：

```text
Phase 2.1：检索深度调控 ✅ 已完成（research-strategies skill）
  - 扩展 web_search / kb_search 支持质量/数量/长度参数
  - 新增"检索策略"逻辑：按文档类型选择检索深度
  - 检索结果结构化存储（供后续大纲规划使用）

Phase 2.2：大纲规划器 ✅ 已完成（outline-planner skill）
  - 定义文档类型模板（产品介绍/技术调研/新闻日报/数据分析）
  - 根据检索结果 + 文档类型生成结构化大纲
  - 大纲含每节标题、摘要、预计字数、所需数据点
  - HITL 确认大纲

Phase 2.3：逐节撰写子智能体 ✅ 已完成（section-writer skill + 子 agent）
  - 新增 section_writer subagent
  - 上下文注入：完整大纲 + 已完成节摘要 + 当前节位置 + 待写节标题
  - 支持顺序模式和并行模式
  - 逐节输出 md 内容，写入中间文件

Phase 2.4：自动 Review + 局部返工 ✅ 已完成（auto-review skill）
  - 新增 auto_review 逻辑：对照需求+大纲，检查 5 个维度
  - 生成修改计划（标注位置+建议，按严重程度排序 P0-P5）
  - 局部修改执行（只改问题节，不重写全文）
  - 修改后重新 Review 受影响节段

Phase 2.5：HTML 制作工作流 ✅ 已完成（md-to-pdf skill）
  - 每页内容(md) → 呈现方式描述(md) → HTML 制作
  - 复用 md-to-pdf 的模板体系 + web-viz-libraries 的可视化能力
  - HTML 审查 → 返工 → 完成
  - HTML → PDF（render_pdf.py）

Phase 2.6：端到端集成 ✅ 已完成（document-builder skill）
  - document-builder Skill 整合上述 5 个 Phase
  - 完整工作流：检索 → 大纲 → 逐节撰写 → Review → 返工 → HTML → PDF
  - HITL 检查点：大纲确认、终稿确认
```

目标是验证文档生成的完整闭环：从用户一句话到结构化 PDF。

### MVP 3：Skill Registry + Skill 独立服务

拆出 Document Builder 为独立服务：

```text
Agent Orchestrator
  ↓
Skill Registry
  ↓
document-builder-service
```

目标是验证 Agent Core 与垂直能力解耦。

### MVP 4：多 Skill 微服务 + 异步任务队列

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

文档生成（HTML → PDF）：
- Playwright headless（已有 render_pdf.py）
- md-to-pdf 模板体系（已有）
- echarts / Three.js / D3（已有 web-viz-libraries skill）
```

选择原则：

- 先验证端到端流程，再引入重型基础设施。
- Agent Core 不依赖具体渲染库。
- Skill 协议要稳定，内部实现可以迭代。
- 长任务优先异步化。

## 11. 质量审查标准

文档交付前至少检查：

内容质量：

- 是否符合用户目标和受众；
- 是否跑题；
- 是否有逻辑断层；
- 是否章节重复；
- 是否关键结论明确。

事实质量：

- 关键数据是否有来源；
- 是否使用过时信息；
- 是否区分事实、推断和建议；
- 是否记录引用。

连贯性质量：

- 章节间是否有逻辑过渡；
- 概念定义是否前后一致；
- 数据引用是否前后一致；
- 是否有矛盾论述。

版式质量：

- 标题层级是否一致；
- 字体、颜色、间距是否统一；
- 图表是否清晰；
- 页面留白是否合理；
- 导出文件是否可打开。

交付质量：

- 是否生成 PDF；
- 是否生成预览图；
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
短期（MVP 2）✅ 已完成：
  单体 Orchestrator + Document Builder Skill（本地模块化）
  已实现：检索深度调控 → 大纲规划 → 逐节撰写 → 自动Review → 返工 → HTML → PDF
  5 个 Phase 通过 document-builder skill 整合为端到端编排

中期（MVP 3）：
  Skill Registry + Document Builder 独立服务

长期（MVP 4）：
  多 Skill 微服务 + 异步队列 + 对象存储 + 沙箱 + 可观测性
```

最重要的长期约束：

```text
扩展运行环境和 Skill 能力，不污染 Agent Core。
```
