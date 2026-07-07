---
name: document-builder
description: "文档生成端到端编排 skill。把用户的一句话需求(如'做一份 AI Agent 技术调研 PDF')变成结构化 PDF。负责整合检索深度调控(research-strategies)→ 大纲规划(outline-planner)→ 逐节撰写(section-writer)→ 自动 Review(auto-review)→ 局部返工 → HTML 制作(md-to-pdf)→ PDF 交付的完整闭环。支持产品介绍/技术调研/新闻日报/数据分析 4 种文档类型。不用于单一环节(仅检索/仅渲染),不用于 PPT/网页原型。"
allowed-tools: task read_file write_file edit_file execute
---

# Document Builder 文档生成端到端编排

把用户的一句话需求变成结构化 PDF,整合 Phase 2.1-2.5 的完整能力。

```
用户需求
  ─[Phase 2.1: 检索深度调控]─► research-agent 检索 → /tmp/research/*.md
  ─[Phase 2.2: 大纲规划]─► outline-planner 两阶段 → /tmp/outline.md
  ─[Checkpoint 1: 大纲确认]─► 用户确认
  ─[Phase 2.3: 逐节撰写]─► section-writer Map-Reduce → /tmp/sections/*.md
  ─[Phase 2.4: 自动 Review]─► auto-review 5 维度 → /tmp/review_report.md
  ─[Phase 2.4: 局部返工]─► 按问题清单修改 → 更新 /tmp/sections/*.md
  ─[Phase 2.5: HTML 制作]─► md-to-pdf 设计+渲染 → output/document.html
  ─[Checkpoint 2: 终稿确认]─► 用户确认
  ─[Phase 2.5: PDF 渲染]─► render_pdf.py → output/document.pdf
```

**核心定位:流程编排 skill**,自己不检索、不渲染,只负责把 5 个 Phase 串起来,并在关键节点设置 HITL 检查点。检索能力由 research-agent 子 agent 提供,撰写能力由 section-writer 子 agent 提供,渲染能力由 md-to-pdf skill 提供。

---

## 何时使用本 skill

| 场景 | 用本 skill? |
|---|---|
| "帮我做一份 XX 主题的 XX 类型 PDF" | ✅ 正是本 skill 的核心场景 |
| "做一份技术调研报告 / 产品介绍 / 数据分析 / 新闻日报 PDF" | ✅ 4 种文档类型都支持 |
| "把这几个 MD 合成一个 PDF" | ❌ 直接用 `md-to-pdf`(已有内容,无需检索+撰写) |
| "帮我查一下 XX 的资料" | ❌ 直接委托 research-agent(无需文档生成) |
| "做个 PPT / 网页原型" | ❌ 本 skill 只做 PDF |
| "总结今天的 AI 新闻" | ⚠️ 接近 `daily-report` skill,但本 skill 更通用(支持任何文档类型) |

> **与 daily-report 的关系**:daily-report 是新闻日报的专用 skill(维度拆解+并行检索)。本 skill 是通用文档生成 skill,支持 4 种文档类型。接到新闻日报需求时,若用户要"日报格式"用 daily-report,若要"通用技术报告格式"用本 skill。

---

## 4 种文档类型

| 类型 | 代号 | 默认深度 | 典型结构 |
|---|---|---|---|
| 产品介绍 | `product_brief` | standard | 概述→核心功能→定价→优劣势→竞品对比→总结 |
| 技术调研 | `tech_research` | in-depth | 概述→技术原理→主流方案对比→落地场景→趋势展望 |
| 新闻日报 | `news_daily` | brief | 头条→产品发布→资本动态→技术突破→开源项目→趋势 |
| 数据分析 | `data_analysis` | in-depth | 概述→数据来源→关键指标→趋势分析→结论建议 |

详细结构模板见 `outline-planner/references/doc-type-templates.md`,检索策略见 `research-strategies/references/doc-type-strategies.md`。

---

## 完整工作流程

### Step 0:需求理解与文档类型判定

从用户需求解析:

```
- 文档类型:product_brief / tech_research / news_daily / data_analysis
- 主题:用户要写什么
- 目标受众:技术决策者 / 普通读者 / 学术评审 / 内部团队
- 目标页数:用户指定或按类型默认(技术调研 12-20 页,产品介绍 8-12 页)
- 深度等级:用户显式说明 > 按文档类型默认
- 特殊要求:是否需要图表、是否需要引用、纸张大小等
```

若用户需求模糊(如"做个报告"),用 AskUserQuestion 确认文档类型和主题。明确后存档:

```
write_file(path="/research_request.md", content="<用户原始需求 + 文档类型 + 深度等级 + 受众 + 页数>")
```

### Step 1:委托检索(Phase 2.1 - 检索深度调控)

读 `research-strategies/SKILL.md` 确认对应文档类型的检索策略,然后委托检索:

```
1. 判断深度等级:
   - 用户显式说明("详细的""简报")→ 按说明
   - 未说明 → 按文档类型默认(tech_research/data_analysis=in-depth,product_brief=standard,news_daily=brief)
2. task(subagent_type="research-agent") 委托检索:
   - description 注明:"<doc_type> <depth>: <主题>"
   - 一次一个明确主题,多主题可并行(最多 3 个并发)
   - research-agent 按 research-strategies 两阶段检索,落盘到 /tmp/research/<topic>.md
3. 检索 Review(主 Agent 对照策略审查):
   - 覆盖度:策略要求的关键词/维度都搜了吗?
   - 相关性:结果和主题相关吗?
   - 来源质量:权威来源占比够吗?
   - 数量:结果条数达到策略要求吗?
   不吻合 → 再派一轮,最多补检 2 轮
```

### Step 2:大纲规划(Phase 2.2 - 两阶段规划)

读 `outline-planner/SKILL.md`,按两阶段规划大纲:

```
Step 2a:表达什么(What to say)
  - read_file /tmp/research/*.md 读取检索素材
  - 按文档类型模板(references/doc-type-templates.md)生成结构化大纲
  - 每节含:标题/摘要/预计字数/所需数据点/来源引用编号
  - write_file /tmp/outline.md

Step 2b:怎么表达(How to present)
  - 逐节审视,挑选最佳表达方式(表格/图表/流程图/概念图/对比矩阵/数据卡片)
  - 更新 /tmp/outline.md,每节增加"呈现方式"标注
  - 注意 PDF 兼容:目标输出 PDF 时不用 WebGL 类库(Three.js/Matter.js 等)
```

### Step 3:🛑 HITL Checkpoint 1 - 大纲确认

```
将 /tmp/outline.md 完整展示给用户:
- 章节结构是否合理?
- 每节的表达方式是否恰当?
- 是否需要增删章节或调整表达方式?

用户要求调整 → 修改大纲 → 重新确认
用户确认 → 进入逐节撰写
```

> **必须真的等用户确认**,不要说完就开干。大纲是文档骨架,改大纲比改正文成本低 10 倍。

### Step 4:逐节撰写(Phase 2.3 - Map-Reduce)

读 `section-writer/SKILL.md`,按 Map-Reduce 模式逐节撰写:

```
Map 阶段(并行):
  - 一条消息发 N 个 task(subagent_type="section-writer")
  - 每个 description 注入:
    · 完整大纲(所有节标题+摘要+呈现方式)
    · 当前节详情(标题/摘要/预计字数/所需数据点/来源/呈现方式)
    · 检索素材路径(/tmp/research/*.md)
    · 全局约定(术语表、引用编号规则)
  - 各子 agent 并行写 /tmp/sections/<section_n>.md
  - 注意:不能一口气让一个 agent 写全部章节,必须逐节分开

Reduce 阶段(串行):
  - 全部完成后 read_file 所有 /tmp/sections/*.md
  - 检查并修正:
    · 章节间过渡句(承上启下,避免突兀跳转)
    · 术语一致性(同一概念不同节用词统一)
    · 引用编号统一(跨节去重,统一重编号)
    · 数据前后矛盾(交叉验证关键数据)
  - 修正后更新对应 /tmp/sections/*.md
```

### Step 5:自动 Review(Phase 2.4 - 5 维度审查)

读 `auto-review/SKILL.md`,执行 Review:

```
1. read_file /tmp/outline.md + /tmp/sections/*.md + 用户原始需求
2. 按 5 维度审查:
   - 需求满足度:用户要的东西都覆盖了吗?
   - 大纲吻合度:实际内容与大纲一致吗?
   - 事实准确性:关键数据有来源吗?过时了吗?
   - 连贯性:章节间逻辑通顺吗?有矛盾吗?
   - 完整性:有没有空节、占位符、TODO 残留?
3. 生成问题清单,按严重程度分级(P0-P5)
4. write_file /tmp/review_report.md
```

### Step 6:局部返工(Phase 2.4 - 仅当 Review 不通过时)

```
返工决策:
- 存在 P0/P1/P2 → 必须返工
- 仅 P3/P4 → 返工受影响节段
- 仅 P5 → 跳过,在 HTML 阶段顺手修
- 全部通过 → 直接进入 HTML 制作

返工执行(按问题类型):
- P0 事实错误(单点)→ edit_file 直接修正
- P1 需求缺失(整节缺)→ task(section-writer) 补写
- P2 大纲偏离(整节跑题)→ task(section-writer) 重写
- P3 连贯问题(跨节)→ edit_file 统一术语/数据
- P4 完整性(占位符)→ edit_file 补全或标注

返工后重新 Review 受影响节段,更新 /tmp/review_report.md。
最多 2 轮返工,仍有问题则标注遗留问题继续。
```

### Step 7:HTML 制作(Phase 2.5 - 设计 + 渲染)

读 `md-to-pdf/SKILL.md`,按其工作流制作 HTML:

```
1. 参考选型:
   - 翻 md-to-pdf/references/showcase/{lite,medium,paper}/sample.html 选范式
   - 从 references/component-catalog.md 挑零件
   - 设计 HTML 骨架(分区+组件选型+配色)
2. 🛑 声明并预览设计(Checkpoint):
   - 告诉用户"我打算用这套范式 + 组件选型 + 配色"
   - 等用户确认后再写 HTML
3. 合并各节内容为单一 MD(必须用脚本,禁止手动拼接):
   execute(command="python skills/md-to-pdf/scripts/merge_sources.py --inputs '[\"/tmp/sections/section_1.md\",\"/tmp/sections/section_2.md\",...]' --strategy sequential --out /tmp/merged.md")
   - ⚠️ 必须用 merge_sources.py,不要用 read_file 手动读各节再拼接——脚本会重写相对图片路径为 file:// 绝对路径,手动拼接会让 section-writer 写的相对图片路径失效(丢图根因)
   - 合并后核对输出里的图片计数行:"图片:源共 N 张,合并后 M 张"。若 M < N 且未传 --strip-images,会打印 [WARN],必须排查重跑
   - 单节文档可跳过此步,直接用 /tmp/sections/section_1.md 作为输入 MD
4. write_file output/document.html:
   - 输入 MD 是上一步合并后的 /tmp/merged.md(或单节场景的 section_1.md)
   - 把占位符 {{chart:...}} 替换为实际 HTML 可视化组件(echarts svg renderer)
   - CSS 全 inline,自包含
   - 图片包 figure 控尺寸,公式转 HTML 实体
   - 图片路径已是 file:// 绝对路径(merge 阶段重写过),HTML 里原样保留
5. 🛑 HTML 预览检查点:
   - 让用户看 HTML(浏览器打开或截图)
   - 确认排版方向/字号/配色/分页/公式/图片尺寸
   - 用户确认后再渲染 PDF
```

### Step 8:🛑 HITL Checkpoint 2 - 终稿确认

```
PDF 渲染前,把最终内容(HTML 预览)展示给用户:
- 内容是否完整?
- 排版是否满意?
- 是否需要调整?

用户要求调整 → 回 Step 4/5/7 对应环节修改
用户确认 → 渲染最终 PDF
```

> **终稿确认是交付前的最后一道关**。PDF 渲染耗时,渲染后再改成本高。

### Step 9:PDF 渲染与交付(Phase 2.5 - Playwright)

```
1. 渲染 PDF:
   execute(command="python skills/md-to-pdf/scripts/render_pdf.py --html output/document.html --out output/document.pdf --page-size A4")

2. 验证:
   execute(command="python skills/md-to-pdf/scripts/render_pdf.py --verify output/document.pdf")
   - 文件大小 > 0
   - 页数符合预期
   - 首尾页截图正常

3. 交付汇报:
   - PDF 路径
   - 页数 + 文件大小
   - 覆盖的主题/章节
   - 引用来源数
   - 质量报告路径(若有)
```

---

## HITL 检查点汇总

| 检查点 | 位置 | 内容 | 跳过条件 |
|---|---|---|---|
| **Checkpoint 1: 大纲确认** | Step 3 | 展示完整大纲(含表达方式)给用户 | 用户需求极简("你看着办") |
| **Checkpoint 2: HTML 设计确认** | Step 7 | 声明范式+组件+配色,等用户确认 | 用户已指定范式("用论文格式") |
| **Checkpoint 3: HTML 预览** | Step 7 | 让用户看 HTML,确认排版 | 用户不看 HTML("直接出 PDF") |
| **Checkpoint 4: 终稿确认** | Step 8 | PDF 渲染前最终确认 | 用户已多次确认("别问了直接做") |

> **默认行为**:Checkpoint 1 和 Checkpoint 4 必须停(大纲和终稿是关键决策)。Checkpoint 2/3 根据用户参与意愿灵活。

---

## 输出约定

| 类型 | 路径 | 说明 |
|---|---|---|
| 最终 PDF | `output/document.pdf` | 交付给用户 |
| 最终 HTML | `output/document.html` | 中间产物,可预览 |
| 大纲 | `/tmp/outline.md` | 含表达方式标注 |
| 各节内容 | `/tmp/sections/<section_n>.md` | 逐节撰写产出 |
| Review 报告 | `/tmp/review_report.md` | 含问题清单+返工记录 |
| 检索素材 | `/tmp/research/<topic>.md` | research-agent 落盘 |
| 原始需求存档 | `/research_request.md` | 用户需求+文档类型+深度+受众 |

---

## 与其他 skill 的协作

本 skill 是**编排者**,整合以下 5 个 Phase 的能力:

| Phase | Skill / Subagent | 职责 |
|---|---|---|
| 2.1 检索深度调控 | `research-strategies` + `research-agent` 子 agent | 按文档类型+深度等级执行两阶段检索 |
| 2.2 大纲规划 | `outline-planner` | 两阶段规划:表达什么 → 怎么表达 |
| 2.3 逐节撰写 | `section-writer` skill + `section-writer` 子 agent | Map-Reduce 逐节撰写,全局进度感知 |
| 2.4 自动 Review | `auto-review` | 5 维度审查 + 局部返工 |
| 2.5 HTML 制作 | `md-to-pdf` | 设计 HTML + Playwright 渲染 PDF |

```
用户需求
  ↓
本 skill(编排)
  ├── 读 research-strategies → 委托 research-agent(检索)
  ├── 读 outline-planner → 规划大纲 → [Checkpoint 1]
  ├── 读 section-writer → 委托 section-writer(逐节撰写)
  ├── 读 auto-review → Review → 返工(如需)
  ├── 读 md-to-pdf → 设计 HTML → [Checkpoint 2] → 渲染 PDF
  └── 交付 output/document.pdf
```

典型链路:用户一句话需求 → 本 skill 编排 5 个 Phase → 交付结构化 PDF。
