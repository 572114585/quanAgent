---
name: outline-planner
description: "大纲规划方法论。检索完成后，主 Agent 读取本 skill 执行两阶段大纲规划：Step1 根据检索内容+文档类型+用户需求生成'表达什么'的大纲；Step2 根据大纲+输出形式挑选'怎么表达'（图表/表格/流程图等），补充到大纲。两步完成后展示给用户确认。"
allowed-tools: read_file write_file
---

# Outline Planner 大纲规划方法论

本 skill 是**方法论参考文档**，主 Agent 在检索 Review 通过后读取本文件，按两阶段流程规划大纲。

详细文档类型模板见 `references/doc-type-templates.md`。

## A. 两阶段流程

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

### 为什么分两阶段？

- **Step1 聚焦内容**：先想清楚"要讲什么"，不被呈现方式干扰，确保内容完整有逻辑。
- **Step2 聚焦形式**：内容定下来后再想"怎么呈现最好"，避免边写边改表达方式导致混乱。
- **用户一次确认**：两步合并展示，用户看到的是"内容+形式"完整的规划，决策更高效。

## B. Step 1 详细：表达什么

### 输入

- `read_file /tmp/research/*.md` 读取所有检索素材
- 文档类型（product_brief / tech_research / news_daily / data_analysis）
- 用户原始需求（目标页数、受众、重点等）

### 流程

1. 按文档类型读取 `references/doc-type-templates.md` 中的结构模板
2. 综合检索内容，判断哪些内容该放进哪些章节
3. 生成大纲，每节包含：
   - 标题
   - 摘要（本节要讲什么，2-3 句）
   - 预计字数
   - 所需数据点（如"需要 AI Agent 市场规模数据"）
   - 来源引用编号（对应 /tmp/research/*.md 中的来源）

### 大纲 md 格式示例

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
- 摘要：对比 LangChain / AutoGPT / CrewAI 等主流框架
- 预计字数：1200
- 所需数据点：框架功能矩阵、性能 benchmark
- 来源：[6][7][8]
```

### Step 1 产出

写入 `/tmp/outline.md`。

## C. Step 2 详细：怎么表达

### 输入

- `/tmp/outline.md`（Step 1 产出）
- 目标输出形式（PDF — 注意 WebGL 类库不兼容 PDF）

### 流程

1. 逐节审视大纲内容
2. 判断该节内容适合什么表达方式（参考下方表达方式清单）
3. 在大纲每节末尾补充"呈现方式"标注
4. 考虑全文表达方式的分布均衡（不要全图表也不要全文字）

### 表达方式标注格式

```markdown
## 2. 技术原理
- 摘要：解析 AI Agent 的核心技术架构（感知-规划-执行-学习）
- 预计字数：1500
- 所需数据点：架构图、关键技术组件
- 来源：[2][4][5]
- 呈现方式：概念图（架构层级关系）+ 流程图（感知-规划-执行-学习循环）
```

### Step 2 产出

更新 `/tmp/outline.md`，每节增加"呈现方式"标注。

## D. 表达方式清单

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

## E. 表达方式选择原则

1. **内容驱动**：表达方式服务于内容，不是为了花哨而加图表
2. **适度原则**：不是每节都要图表，关键节用图表，论述节用文字
3. **分布均衡**：全文图表占比建议 30-50%（技术调研偏高，新闻日报偏低）
4. **PDF 优先**：目标输出 PDF 时，不用 WebGL 类库
5. **数据匹配**：有数据→图表/表格；有过程→流程图；有层级→概念图；有对比→对比矩阵

## F. HITL 确认

两步完成后，将 `/tmp/outline.md` 完整展示给用户：

```
大纲已规划完成（含表达方式），请确认：
1. 章节结构是否合理？
2. 每节的表达方式是否恰当？
3. 是否需要增删章节或调整表达方式？
确认后进入逐节撰写。
```

- 用户要求调整 → 修改大纲 → 重新确认
- 用户确认 → 进入逐节撰写（Phase 2.3）

## G. 使用指引（给主 Agent）

```
1. 检索 Review 通过后，读取本 SKILL.md
2. 确定文档类型（product_brief / tech_research / news_daily / data_analysis）
3. 读取 references/doc-type-templates.md 获取对应结构模板
4. 执行 Step 1：综合检索内容 → 按模板生成大纲 → 写入 /tmp/outline.md
5. 执行 Step 2：逐节挑选表达方式 → 更新 /tmp/outline.md
6. 展示完整大纲给用户确认
7. 用户确认后 → 进入逐节撰写
```
