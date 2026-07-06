# Phase 2.2：大纲规划器 — 详细设计

## Summary

新建 outline-planner skill，供主 Agent 在检索完成后执行两阶段大纲规划：Step 1 根据检索内容+文档类型+用户需求生成"表达什么"的大纲 md；Step 2 根据大纲+目标输出形式挑选"怎么表达"（图表/表格/概念图/流程图/对比矩阵/数据卡片/3D 等），补充到大纲 md。两步完成后一次 HITL 确认。同时在 SYSTEM_PROMPT 新增大纲规划原则。

## Current State Analysis

### 当前大纲相关实现

| 维度 | 现状 | 问题 |
|---|---|---|
| 大纲规划 | daily-report skill 的 Step 5 有简单大纲，但仅限日报 | 无通用大纲规划能力 |
| 文档类型模板 | 无 | 产品介绍/技术调研/新闻日报/数据分析各有不同结构需求 |
| 表达方式选择 | 无 | 当前正文全文字，不会主动选图表/表格/流程图等 |
| HITL 确认 | daily-report 有 Checkpoint | 但仅限日报，无通用机制 |
| subagent | 只有 research_subagent | 大纲规划由主 Agent 自己做（用户已确认），不新增 subagent |

### 关键文件

- [agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) — SYSTEM_PROMPT（L11-35），需新增大纲规划原则
- [agent_core/runtime.py](file:///d:/project/agent_core/runtime.py#L130-L139) — build_agent()，skills 自动加载，无需改
- [workspace/skills/research-strategies/SKILL.md](file:///d:/project/workspace/skills/research-strategies/SKILL.md) — 刚建的策略 skill，结构参考
- [workspace/skills/daily-report/SKILL.md](file:///d:/project/workspace/skills/daily-report/SKILL.md) — 现有日报 skill，大纲结构参考
- [workspace/skills/web-viz-libraries/SKILL.md](file:///d:/project/workspace/skills/web-viz-libraries/SKILL.md) — 表达方式的库选择参考（echarts/Three.js 等）

### 用户确认的决策

1. **执行者**：主 Agent 自己执行（不新增 subagent）
2. **HITL 确认点**：两步完成后一次确认（Step 1 表达什么 + Step 2 怎么表达 → 合并展示 → 用户确认）
3. **表达方式**：基础集合（表格/图表/流程图/概念图/时间线）+ 对比矩阵 + 数据卡片/引用块 + 3D/动画

## Proposed Changes

### 改动 1：新建 outline-planner skill

**文件**：新建 `workspace/skills/outline-planner/SKILL.md` + `references/doc-type-templates.md`

**What**：大纲规划方法论 skill。主 Agent 在检索完成后读取本 skill，按两阶段流程规划大纲。

**Why**：当前无通用大纲规划能力，不同文档类型需要不同结构，且需要主动选择表达方式（图表/表格/流程图等）而非全文字。

**目录结构**：
```
workspace/skills/outline-planner/
├── SKILL.md                            # 入口：两阶段流程 + 表达方式清单 + 使用指引
└── references/
    └── doc-type-templates.md           # 4 种文档类型的结构模板
```

**SKILL.md 内容大纲**：

```yaml
---
name: outline-planner
description: "大纲规划方法论。检索完成后，主 Agent 读取本 skill 执行两阶段大纲规划：Step1 根据检索内容+文档类型+用户需求生成'表达什么'的大纲；Step2 根据大纲+输出形式挑选'怎么表达'（图表/表格/流程图等），补充到大纲。两步完成后展示给用户确认。"
allowed-tools: read_file write_file
---
```

**主体内容结构**：

#### A. 两阶段流程

```
Step 1：表达什么（What to say）
  输入：检索内容（/tmp/research/*.md）+ 文档类型 + 用户需求
  动作：综合检索内容 → 按文档类型模板 → 生成结构化大纲
  产出：/tmp/outline.md（含每节标题、摘要、预计字数、所需数据点）

Step 2：怎么表达（How to present）
  输入：/tmp/outline.md + 目标输出形式（PDF）
  动作：逐节审视 → 挑选最佳表达方式 → 补充到大纲每节
  产出：/tmp/outline.md 更新（每节增加"呈现方式"标注）

→ HITL 确认：展示完整大纲（含呈现方式）给用户
```

#### B. Step 1 详细：表达什么

输入：
- `read_file /tmp/research/*.md` 读取所有检索素材
- 文档类型（product_brief / tech_research / news_daily / data_analysis）
- 用户原始需求（目标页数、受众、重点等）

流程：
1. 按文档类型读取 `references/doc-type-templates.md` 中的结构模板
2. 综合检索内容，判断哪些内容该放进哪些章节
3. 生成大纲，每节包含：
   - 标题
   - 摘要（本节要讲什么，2-3 句）
   - 预计字数
   - 所需数据点（如"需要 AI Agent 市场规模数据"）
   - 来源引用编号（对应 /tmp/research/*.md 中的来源）

大纲 md 格式示例：
```markdown
# AI Agent 行业技术调研报告

## 1. 概述
- 摘要：介绍 AI Agent 的定义、发展背景和报告范围
- 预计字数：500
- 所需数据点：AI Agent 定义、发展时间线
- 来源：[1][3]

## 2. 技术原理
- 摘要：解析 AI Agent 的核心技术架构（感知-规划-执行-学习）
- 预计字数：1500
- 所需数据点：架构图、关键技术组件
- 来源：[2][4][5]

## 3. 主流框架对比
...
```

#### C. Step 2 详细：怎么表达

输入：
- `/tmp/outline.md`（Step 1 产出）
- 目标输出形式（PDF — 注意 WebGL 类库不兼容 PDF）

流程：
1. 逐节审视大纲内容
2. 判断该节内容适合什么表达方式（参考下方表达方式清单）
3. 在大纲每节末尾补充"呈现方式"标注
4. 考虑全文表达方式的分布均衡（不要全图表也不要全文字）

表达方式标注格式：
```markdown
## 2. 技术原理
- 摘要：解析 AI Agent 的核心技术架构（感知-规划-执行-学习）
- 预计字数：1500
- 所需数据点：架构图、关键技术组件
- 来源：[2][4][5]
- 呈现方式：概念图（架构层级关系）+ 流程图（感知-规划-执行-学习循环）
```

#### D. 表达方式清单

| 表达方式 | 适用场景 | PDF 兼容 | 实现库 |
|---|---|---|---|
| 纯文字段落 | 论述、分析、总结 | ✅ | 无 |
| 表格 | 对比、结构化数据 | ✅ | HTML table |
| 柱状图/折线图/饼图 | 数据趋势、占比、对比 | ✅ | echarts (svg renderer) |
| 流程图 | 过程、步骤、循环 | ✅ | echarts graph / mermaid |
| 概念图/思维导图 | 层级关系、概念关联 | ✅ | echarts tree / mermaid |
| 时间线 | 发展历程、里程碑 | ✅ | echarts timeline / 自定义 |
| 对比矩阵 | 多维度方案对比 | ✅ | HTML table |
| 数据卡片 | 关键数字突出展示 | ✅ | HTML card layout |
| 引用块 | 高亮引述、重点结论 | ✅ | HTML blockquote |
| 关系图 | 节点连线关系 | ✅ | echarts graph |
| 3D 场景 | 产品展示、空间关系 | ❌ 仅交互 HTML | Three.js |
| 物理动画 | 动态演示 | ❌ 仅交互 HTML | Matter.js |

> **PDF 输出约束**：WebGL 类库（Three.js / Matter.js / Spline / Rive / Shadertoy）不能进入 PDF 打印流。如目标输出为 PDF，只用 PDF 兼容的表达方式。3D/动画仅用于交互式 HTML 交付场景。
> 详见 `skills/web-viz-libraries/SKILL.md` 的"Delivery Scenario Compatibility"表。

#### E. 表达方式选择原则

1. **内容驱动**：表达方式服务于内容，不是为了花哨而加图表
2. **适度原则**：不是每节都要图表，关键节用图表，论述节用文字
3. **分布均衡**：全文图表占比建议 30-50%（技术调研偏高，新闻日报偏低）
4. **PDF 优先**：目标输出 PDF 时，不用 WebGL 类库
5. **数据匹配**：有数据→图表/表格；有过程→流程图；有层级→概念图；有对比→对比矩阵

#### F. HITL 确认

两步完成后，将 `/tmp/outline.md` 完整展示给用户：
```
大纲已规划完成（含表达方式），请确认：
1. 章节结构是否合理？
2. 每节的表达方式是否恰当？
3. 是否需要增删章节或调整表达方式？
确认后进入逐节撰写。
```

用户要求调整 → 修改大纲 → 重新确认
用户确认 → 进入 Phase 2.3（逐节撰写）

**references/doc-type-templates.md**：4 种文档类型的结构模板，每种含典型章节、每节说明、建议表达方式。

---

### 改动 2：references/doc-type-templates.md 内容

**4 种文档类型模板**：

#### 产品介绍（product_brief）
```
1. 产品概述（定义、定位、核心价值）→ 表达方式：数据卡片
2. 核心功能（功能列表+说明）→ 表达方式：表格
3. 定价体系（价格档位对比）→ 表达方式：对比矩阵
4. 优劣势分析（优点/缺点）→ 表达方式：表格
5. 竞品对比（与同类产品对比）→ 表达方式：对比矩阵
6. 使用场景（典型用例）→ 表达方式：纯文字
7. 总结与建议 → 表达方式：纯文字
```

#### 技术调研（tech_research）
```
1. 概述（背景、定义、报告范围）→ 表达方式：纯文字
2. 技术原理（架构、核心机制）→ 表达方式：概念图 + 流程图
3. 主流框架（框架列表+特点）→ 表达方式：表格
4. 对比分析（性能/功能/生态对比）→ 表达方式：对比矩阵 + 柱状图
5. 落地场景（应用案例）→ 表达方式：纯文字
6. 发展趋势（未来方向）→ 表达方式：时间线
7. 结论与建议 → 表达方式：纯文字
```

#### 新闻日报（news_daily）
```
1. 头条（1-2 条重大事件）→ 表达方式：引用块
2. 产品/模型发布 → 表达方式：纯文字 + 数据卡片
3. 资本动态 → 表达方式：表格
4. 技术与论文 → 表达方式：纯文字
5. 开源项目 → 表达方式：表格
6. 趋势预测 → 表达方式：纯文字
7. Sources → 表达方式：纯文字
```

#### 数据分析（data_analysis）
```
1. 概述（分析背景、数据来源）→ 表达方式：纯文字
2. 市场规模（总量、增长率）→ 表达方式：柱状图 + 数据卡片
3. 细分数据（按维度拆解）→ 表达方式：饼图 + 表格
4. 趋势分析（历史趋势、预测）→ 表达方式：折线图
5. 竞争格局（市场份额）→ 表达方式：饼图 + 对比矩阵
6. 对比分析（同比/环比/横向）→ 表达方式：柱状图 + 表格
7. 结论与建议 → 表达方式：纯文字
```

---

### 改动 3：SYSTEM_PROMPT 新增大纲规划原则

**文件**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) L24-35

**What**：在 SYSTEM_PROMPT 的通用编排原则中新增"大纲规划"原则。

**How**：在"检索结果 Review"原则之后追加：

```python
- **大纲规划两阶段**：检索 Review 通过后，读 skills/outline-planner/SKILL.md 按两阶段规划大纲：
  Step1 表达什么：综合检索内容+文档类型模板+用户需求，生成结构化大纲（每节含标题/摘要/预计字数/所需数据点/来源），写入 /tmp/outline.md
  Step2 怎么表达：逐节审视大纲，按内容挑选最佳表达方式（表格/图表/流程图/概念图/对比矩阵/数据卡片等），补充到 /tmp/outline.md 每节的"呈现方式"标注
  两步完成后展示完整大纲给用户确认，确认后进入逐节撰写。
  注意：目标输出为 PDF 时，不用 WebGL 类库（Three.js/Matter.js 等），只用 echarts(svg)/表格/流程图等 PDF 兼容方式。
```

---

## Assumptions & Decisions

1. **主 Agent 执行**（用户确认）— 不新增 subagent，主 Agent 自己读 skill 执行大纲规划
2. **两步完成后一次确认**（用户确认）— Step1 + Step2 合并展示，用户一次确认
3. **表达方式全套**（用户确认）— 基础集合 + 对比矩阵 + 数据卡片/引用块 + 3D/动画，但 PDF 输出时受限
4. **PDF 兼容性约束**— WebGL 类库不能进 PDF，仅 echarts(svg)/表格/流程图/概念图等可用于 PDF
5. **大纲文件路径**：`/tmp/outline.md`（中间文件，与 daily-report 约定一致）
6. **文档类型 4 种**：product_brief / tech_research / news_daily / data_analysis（与 research-strategies 一致）
7. **skill 是方法论参考**（非执行代码）— 类似 research-strategies，主 Agent 读取后自行执行
8. **不改 runtime.py**— skills 自动加载，新增 skill 文件即自动注册

## Verification Steps

### 验证改动 1+2（outline-planner skill）

1. `read_file skills/outline-planner/SKILL.md` 能正常读取
2. 两阶段流程描述清晰（Step1 表达什么 → Step2 怎么表达）
3. 表达方式清单完整（12 种，标注 PDF 兼容性）
4. `references/doc-type-templates.md` 含 4 种文档类型模板，每种含章节+建议表达方式

### 验证改动 3（SYSTEM_PROMPT）

1. 语法检查通过
2. 新增原则位于"检索结果 Review"之后
3. 内容包含两阶段说明 + HITL 确认 + PDF 兼容性约束

### 端到端验证

对 LLM 说："帮我做一份详细的 AI Agent 行业技术调研报告"：
1. 主 Agent 检索 → Review 通过
2. 读 outline-planner/SKILL.md
3. Step1：读 /tmp/research/*.md → 按技术调研模板生成 /tmp/outline.md
4. Step2：逐节挑选表达方式（如"技术原理"节加概念图+流程图）→ 更新 /tmp/outline.md
5. 展示完整大纲给用户确认

---

## 不做的事

- ❌ 不新增 outline-planner subagent — 主 Agent 自己执行（用户确认）
- ❌ 不改 runtime.py — skills 自动加载
- ❌ 不做逐节撰写（Phase 2.3 范围）
- ❌ 不做自动 Review（Phase 2.4 范围）
- ❌ 不做 HTML 制作（Phase 2.5 范围）
- ❌ 不改 daily-report skill — 它有自己的大纲逻辑，本 skill 是通用的
- ❌ 不做表达方式的代码实现 — skill 只描述"选什么"，实现由后续 Phase 的 HTML 制作完成
