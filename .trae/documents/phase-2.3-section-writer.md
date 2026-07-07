# Phase 2.3：逐节撰写子智能体 — 详细设计

## Summary

新建 section-writer subagent，采用 **Map-Reduce + 文件系统黑板** 模式实现并行逐节撰写：Map 阶段主 Agent 一条消息并行发 N 个 task()，每个 subagent 的 description 预注入完整大纲+当前节详情+检索素材路径+全局约定，各 subagent 独立写 /tmp/sections/<n>.md；Reduce 阶段主 Agent 串行 read_file 全部章节，修正过渡句/术语一致性/引用统一/数据矛盾。参考 GPT Researcher 的 Map-Reduce 写作模式和 Blackboard 共享黑板模式。

## Current State Analysis

### DeepAgents task() 机制约束（关键）

基于代码探索（[subagents.py L538-539](file:///d:/project/.agent/Lib/site-packages/deepagents/middleware/subagents.py#L538-L539)）：

| 约束 | 说明 |
|---|---|
| subagent 看不到主 agent 对话历史 | messages 被重置为 `[HumanMessage(content=description)]` |
| subagent 是无状态一次性的 | 不能多次通信，只返回最终消息 |
| subagent 间不能直接通信 | 并行启动的 subagent 互不可见 |
| **文件系统是共享的** | backend 不在 `_EXCLUDED_STATE_KEYS` 中，subagent 可读写主 agent 的文件 |
| **支持并行 task()** | 一条 AIMessage 多个 tool_call → langgraph 并发执行 atask 协程 |
| subagent 返回值 | 最后一条非空 AIMessage 文本 → ToolMessage 回父图 |

### 并行 + 信息共享的业界方案

| 模式 | 做法 | 适用性 |
|---|---|---|
| **Blackboard 黑板模式** | 所有 agent 读写共享空间，通过中央状态隐式通信 | 文件系统就是天然黑板 |
| **Map-Reduce**（GPT Researcher / LangGraph） | Map 阶段并行写各节，Reduce 阶段汇总修正 | 完美匹配"逐节并行写+事后统一" |
| **预注入上下文** | 启动前把全局信息注入每个 subagent 的 description | 解决"看不到对话历史"的约束 |

### 本方案：Map-Reduce + 文件黑板 + 预注入

```
Map 阶段（并行写初稿）
  主 Agent 一条消息 → N 个 task(subagent_type="section-writer")
  每个 description 预注入：
    - 完整大纲（所有节标题+摘要+呈现方式）← 全局意识
    - 当前节详情（标题/摘要/预计字数/所需数据点/来源/呈现方式）← 任务定义
    - 检索素材路径（/tmp/research/*.md）← 子 agent 自己 read_file
    - 全局约定（术语表/引用编号规则/文档类型）← 一致性基础
  每个 subagent 独立写 /tmp/sections/<n>.md

Reduce 阶段（串行修正连贯性）
  主 Agent read_file 所有 /tmp/sections/*.md
  主 Agent 做全局修正：
    - 章节间过渡句（承上启下）
    - 术语一致性（统一术语表）
    - 引用编号统一（跨节去重重编号）
    - 数据前后矛盾（交叉验证）
  修正后更新 /tmp/sections/*.md
```

### 关键文件

- [agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) — 新增 section_writer subagent + SYSTEM_PROMPT 新增撰写原则
- [agent_core/runtime.py](file:///d:/project/agent_core/runtime.py#L130-L139) — subagents 列表加入 section_writer
- [workspace/skills/outline-planner/SKILL.md](file:///d:/project/workspace/skills/outline-planner/SKILL.md) — 上游产物 /tmp/outline.md

## Proposed Changes

### 改动 1：新建 section-writer subagent

**文件**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py)

**What**：在 research_subagent 之后新增 section_writer subagent 定义。

**How**：

```python
# 逐节撰写子 agent：按大纲写单节内容，写入 /tmp/sections/
section_writer = {
    "name": "section-writer",
    "description": (
        "撰写文档的单个章节。主 Agent 在 description 中注入完整大纲、当前节详情、"
        "检索素材路径和全局约定。子 agent 读取素材后撰写当前节内容，"
        "写入 /tmp/sections/<section_n>.md，返回章节摘要 + 文件路径。"
        "用于文档生成的逐节并行撰写阶段。"
    ),
    "system_prompt": (
        "你是文档撰写助手，负责撰写文档的某一个章节。\n"
        "接到任务后：\n"
        "1. 从 task description 解析以下信息：\n"
        "   - 文档类型和标题\n"
        "   - 完整大纲（所有节的标题+摘要+呈现方式）\n"
        "   - 当前要写的节（标题、摘要、预计字数、所需数据点、来源引用、呈现方式）\n"
        "   - 检索素材文件路径（/tmp/research/*.md）\n"
        "   - 全局约定（术语表、引用编号规则）\n"
        "2. read_file 读取相关检索素材，提取当前节所需的信息和数据\n"
        "3. 按呈现方式撰写当前节内容：\n"
        "   - 如呈现方式含'图表/流程图/概念图'等，在 md 中用占位符标注（如 {{chart:柱状图-市场规模}}）\n"
        "   - 实际的 HTML 图表制作由后续阶段完成，本阶段只写 md 内容+占位符\n"
        "   - 引用来源用 [编号] 标注，编号对应检索素材中的来源\n"
        "4. 撰写时注意全局连贯性：\n"
        "   - 参考完整大纲，确保本节内容与前后节有逻辑关联\n"
        "   - 不要重复其他节已覆盖的内容\n"
        "   - 术语使用全局约定中的统一术语\n"
        "5. 用 write_file 写入 /tmp/sections/<section_n>.md（n 为节序号）\n"
        "6. 返回简短摘要（本节写了什么 + 字数 + 用了哪些来源）+ 文件路径\n"
        "原则：\n"
        "- 只写分配给你的那一节，不要写其他节\n"
        "- 内容必须有来源支撑，不编造数据\n"
        "- 缺数据用 [此处需要补充: xxx] 占位\n"
        "- 呈现方式占位符格式：{{chart:类型-描述}} / {{table:描述}} / {{flowchart:描述}} / {{concept-map:描述}}\n"
    ),
    "tools": [get_current_time, web_search, kb_search],  # 文件工具由 FilesystemMiddleware 注入
}
```

**关键设计**：
- tools 含 web_search/kb_search（允许子 agent 在撰写时补充查资料，但主要是 read_file 检索素材）
- 呈现方式用占位符 `{{chart:...}}` 标注，不实际生成图表代码（图表由 Phase 2.5 HTML 制作阶段实现）
- 引用编号对应检索素材中的来源编号
- 全局连贯性通过 description 预注入的完整大纲保证

---

### 改动 2：runtime.py 注册 section_writer

**文件**：[agent_core/runtime.py](file:///d:/project/agent_core/runtime.py#L24)

**What**：import section_writer 并加入 subagents 列表。

**How**：

L24 的 import 改为：
```python
from agent_core.prompts import SYSTEM_PROMPT, research_subagent, section_writer
```

L135 的 subagents 改为：
```python
subagents=[research_subagent, section_writer],
```

---

### 改动 3：SYSTEM_PROMPT 新增逐节撰写原则

**文件**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) SYSTEM_PROMPT

**What**：在"大纲规划两阶段"原则之后新增"逐节撰写"原则。

**How**：追加以下内容到 SYSTEM_PROMPT：

```python
- **逐节撰写 Map-Reduce**：用户确认大纲后，按 Map-Reduce 模式逐节撰写：
  Map 阶段（并行）：一条消息发 N 个 task(subagent_type="section-writer")，每个 description 注入：
    · 完整大纲（所有节标题+摘要+呈现方式）
    · 当前节详情（标题/摘要/预计字数/所需数据点/来源/呈现方式）
    · 检索素材路径（/tmp/research/*.md）
    · 全局约定（术语表：列出全文统一术语；引用编号规则：[编号]对应检索素材来源）
  各子 agent 并行写 /tmp/sections/<section_n>.md
  Reduce 阶段（串行）：全部完成后 read_file 所有 /tmp/sections/*.md，检查并修正：
    · 章节间过渡句（承上启下，避免突兀跳转）
    · 术语一致性（同一概念不同节用词统一）
    · 引用编号统一（跨节去重，统一重编号）
    · 数据前后矛盾（交叉验证关键数据）
  修正后更新对应 /tmp/sections/*.md
  注意：不能一口气让一个 agent 写全部章节，必须逐节分开写（并行或串行均可，但每节独立 task）。
```

---

### 改动 4：新建 section-writer skill（撰写方法论）

**文件**：新建 `workspace/skills/section-writer/SKILL.md`

**What**：撰写方法论参考文档。section-writer subagent 和主 Agent 都可查阅。

**Why**：子 agent 的 system_prompt 有字数限制，详细方法论放 skill 文件供需要时 read_file。

**内容大纲**：

```yaml
---
name: section-writer
description: "文档逐节撰写方法论。section-writer 子 agent 撰写单节内容时参考。定义内容撰写规范、呈现方式占位符格式、引用标注规则、全局连贯性要求。"
allowed-tools: read_file write_file
---
```

主体内容：

#### A. 撰写单节流程

```
1. 解析 description 中的信息（大纲/当前节/素材路径/全局约定）
2. read_file 检索素材，提取当前节所需信息
3. 按呈现方式撰写 md 内容（含占位符）
4. write_file 写入 /tmp/sections/<section_n>.md
5. 返回摘要 + 文件路径
```

#### B. 呈现方式占位符格式

| 占位符 | 含义 | 示例 |
|---|---|---|
| `{{chart:类型-描述}}` | 图表占位 | `{{chart:柱状图-2021-2025年市场规模}}` |
| `{{table:描述}}` | 表格占位 | `{{table:主流框架功能对比}}` |
| `{{flowchart:描述}}` | 流程图占位 | `{{flowchart:Agent感知-规划-执行-学习循环}}` |
| `{{concept-map:描述}}` | 概念图占位 | `{{concept-map:AI Agent技术架构层级}}` |
| `{{timeline:描述}}` | 时间线占位 | `{{timeline:AI Agent发展历程2019-2026}}` |
| `{{comparison-matrix:描述}}` | 对比矩阵占位 | `{{comparison-matrix:LangChain vs AutoGPT vs CrewAI}}` |
| `{{data-card:描述}}` | 数据卡片占位 | `{{data-card:全球AI Agent市场规模$50亿}}` |
| `{{quote:内容}}` | 引用块占位 | `{{quote:AI Agent是下一个重大技术范式转变}}` |

> 占位符在 md 中独占一行，后续 HTML 制作阶段会替换为实际的可视化组件。

#### C. 引用标注规则

```
- 引用来源用 [编号] 标注，编号对应 /tmp/research/*.md 中的来源编号
- 示例：AI Agent 市场规模预计 2026 年达到 500 亿美元 [3]
- 多个来源用 [3][5] 标注
- 每节末尾不需要列 Sources（全文统一在最后列）
```

#### D. 全局连贯性要求

```
撰写时参考完整大纲，确保：
1. 不重复其他节已覆盖的内容（如"概述"已定义的概念，"技术原理"不重复定义）
2. 术语使用全局约定中的统一术语
3. 引用编号与其他节一致（同一来源用相同编号）
4. 本节内容与前后节有逻辑关联（如"上一节介绍了原理，本节将对比主流框架"）
```

#### E. 内容质量要求

```
1. 内容必须有来源支撑，不编造数据
2. 缺数据用 [此处需要补充: xxx] 占位
3. 预计字数是大致参考，内容质量优先于字数
4. 数据要标注年份和来源
5. 区分事实、推断和预测
```

---

## Assumptions & Decisions

1. **Map-Reduce 模式**（参考 GPT Researcher + LangGraph）— Map 并行写初稿，Reduce 串行修正连贯性
2. **文件系统黑板**（参考 Blackboard 模式）— /tmp/sections/*.md 作为共享黑板，所有 agent 读写
3. **预注入上下文**（解决 task() 约束）— description 注入完整大纲+当前节详情+素材路径+全局约定
4. **并行不要求实时互见** — 并行写的 subagent 看不到彼此的实时产出，但通过预注入大纲保证全局意识，Reduce 阶段兜底连贯性
5. **呈现方式用占位符** — 本阶段只写 md 内容+占位符，图表代码由 Phase 2.5 HTML 制作实现
6. **新建 section-writer subagent**（用户确认）— 有独立 system_prompt 和 tools
7. **Reduce 由主 Agent 做** — 不新增 reduce subagent，主 Agent read_file 后自己修正
8. **全局约定注入** — 术语表和引用编号规则在 description 中预注入，确保跨节一致

## Verification Steps

### 验证改动 1+2+3（subagent + runtime + prompt）

1. `python -c "import ast; ast.parse(open('agent_core/prompts.py').read()); print('OK')"` 语法通过
2. `python -c "import ast; ast.parse(open('agent_core/runtime.py').read()); print('OK')"` 语法通过
3. runtime.py 的 subagents 列表含 `section_writer`
4. SYSTEM_PROMPT 含"逐节撰写 Map-Reduce"原则

### 验证改动 4（section-writer skill）

1. `read_file skills/section-writer/SKILL.md` 能正常读取
2. 占位符格式表完整（8 种）
3. 撰写流程清晰（5 步）

### 端到端验证

对 LLM 说："帮我做一份详细的 AI Agent 行业技术调研报告"，确认大纲后：
1. 主 Agent 发起 Map 阶段：一条消息发 7 个 task(subagent_type="section-writer")
2. 每个 description 含完整大纲+当前节详情+素材路径+全局约定
3. 7 个 section-writer 并行写 /tmp/sections/1.md ~ 7.md
4. 全部完成后主 Agent 进入 Reduce 阶段
5. read_file 所有 sections，修正过渡句/术语/引用/数据
6. 更新 /tmp/sections/*.md
7. 进入下一阶段（Phase 2.4 自动 Review）

---

## 不做的事

- ❌ 不做自动 Review（Phase 2.4 范围）
- ❌ 不做 HTML 制作（Phase 2.5 范围）
- ❌ 不做图表代码实现 — 本阶段只用占位符标注
- ❌ 不新增 reduce subagent — Reduce 由主 Agent 自己做
- ❌ 不做实时 subagent 间通信 — 用预注入+文件黑板+Reduce 兜底替代
- ❌ 不改 web.py — SSE 已支持并行 subagent 多卡片展示
- ❌ 不限制并行数量 — 由主 Agent 根据大纲节数决定，DeepAgents 无硬限制
