---
name: auto-review
description: "文档自动审查与局部返工方法论。逐节撰写完成后,主 Agent 读取本 skill 执行 Review:对照用户需求+大纲检查 5 个维度(需求满足度/大纲吻合度/事实准确性/连贯性/完整性),生成修改计划(按严重程度排序,优先局部修改),执行返工并重新 Review 受影响节段。"
allowed-tools: read_file inspect_file write_file edit_file replace_file
---

# Auto Review 自动审查与局部返工方法论

本 skill 是**方法论参考文档**,主 Agent 在逐节撰写完成(全部 `/tmp/sections/*.md` 落盘)后读取本文件,按两阶段执行:Review → 返工。

## A. 两阶段流程

```
Step 1：Review(审查)
  输入:/tmp/outline.md(大纲) + /tmp/sections/*.md(各节内容) + 用户原始需求
  动作:逐节逐维度审查 → 生成问题清单
  产出:/tmp/review_report.md(含问题列表 + 严重程度 + 位置 + 修改建议)

Step 2:Rework(返工,仅当 Review 不通过时)
  输入:/tmp/review_report.md + /tmp/sections/*.md
  动作:按问题清单制定修改计划 → 局部修改受影响节 → 重新 Review 受影响节
  产出:更新后的 /tmp/sections/*.md + /tmp/review_report.md 追加返工记录
```

### 何时跳过 Rework

- Review 全部通过(问题清单为空)→ 直接进入 HTML 制作阶段
- 仅存在"表述问题"级别的小瑕疵 → 可在 HTML 阶段顺手修正,不必走 Rework

## B. Step 1 详细:Review 5 维度

### 维度 1:需求满足度

对照用户原始需求(从 `/tmp/research_request.md` 或会话上下文),检查:

```
- 用户要求覆盖的主题都覆盖了吗?
- 目标受众(技术决策者/普通读者/学术评审)的诉求匹配吗?
- 用户指定的重点(如"重点对比框架""侧重数据")有着落吗?
- 文档类型(产品介绍/技术调研/新闻日报/数据分析)的特征要素都有吗?
```

### 维度 2:大纲吻合度

对照 `/tmp/outline.md`,检查:

```
- 大纲规划的章节都写了吗?有没有缺节?
- 每节实际内容与大纲规划的摘要一致吗?有没有跑题?
- 大纲规划的"呈现方式"(图表/流程图/对比矩阵)在 md 中有对应占位符吗?
- 预计字数与实际字数：用 `inspect_file` 读取实际字符数；实际 < 预计的 **70%** → 记为 **P2 字数不足**（必须返工扩写），不再当作 P5
```

### 维度 3:事实准确性

逐节检查数据与引用:

```
- 关键数据(数字、比例、年份)有来源标注 [编号] 吗?
- 标注的来源编号在 /tmp/research/*.md 中能找到对应吗?
- 数据是否过时?(如"2023 年数据"在 2026 年的报告中算过时)
- 有没有"看起来像编造"的精确数字?(无来源的精确数字必须存疑)
- 预测/推断有没有标注"预测""预计"字样?
```

### 维度 4:连贯性

跨节检查逻辑一致性:

```
- 章节间有逻辑过渡吗?(承上启下,还是突兀跳转)
- 同一概念在不同节用词统一吗?(如"AI Agent" vs "智能体"混用)
- 同一数据在不同节引用一致吗?(如 A 节说"市场规模 500 亿",B 节说"450 亿")
- 有没有前后矛盾?(如 A 节说"技术成熟",B 节说"尚不成熟")
- 概念定义有没有重复?(概述已定义的术语,技术原理节又定义一遍)
```

### 维度 5:完整性

检查残留与缺失:

```
- 有没有 [此处需要补充: xxx] 占位符残留?
- 有没有 TODO / TBD / 待完善 标记?
- 有没有空节(只有标题没有内容)?
- 有没有"如下所示"但后面没有跟图表的断裂?
- 占位符 {{chart:...}} / {{table:...}} 描述清晰吗?(能否据此制作 HTML)
```

## C. 问题严重程度分级

按严重程度排序(高 → 低),决定返工优先级:

| 等级 | 说明 | 示例 | 处理 |
|---|---|---|---|
| **P0 事实错误** | 数据错误/编造/来源缺失 | "市场规模 500 亿"无来源 | 必须返工,补来源或删除 |
| **P1 需求缺失** | 用户要求的重点未覆盖 | 用户要"对比框架",实际没写 | 必须返工,补写缺失节 |
| **P2 大纲偏离/字数不足** | 跑题、缺节、或实际字数 < 预计 70% | 预计 2000 字实际 500 字 | 必须返工,补写或扩写 |
| **P3 连贯问题** | 矛盾/术语不统一/过渡缺失 | 前后数据不一致 | 返工受影响节 |
| **P4 完整性问题** | 占位符/TODO 残留 | `[此处需要补充]` 未处理 | 返工补全或标注 |
| **P5 表述问题** | 措辞不佳/小幅润色 | 个别句子生硬 | 可在 HTML 阶段顺手修 |

### 返工决策

```
- 存在 P0/P1/P2 任意一项 → 必须返工
- 仅 P3/P4 → 返工受影响节段
- 仅 P5 → 跳过 Rework,在 HTML 阶段修正
- 全部通过 → 直接进入 HTML 制作
- 注意：字数不足属于 P2，禁止当作 P5 跳过
```

## D. Review 报告格式

用 `replace_file` 写入 `/tmp/review_report.md`:

```markdown
# Review Report

## 审查结论

- 审查时间:<时间>
- 审查范围:<节数> 节
- 结论:❌ 不通过,需返工 / ✅ 通过

## 问题清单

### P0 事实错误

#### [Section 2] 技术原理
- 问题:"AI Agent 市场规模 500 亿美元" 无来源标注
- 位置:/tmp/sections/section_2.md,第 15 行
- 建议:补充来源引用,或删除该数据

### P1 需求缺失

#### 全文
- 问题:用户要求"对比主流框架",实际未覆盖
- 建议:补充"主流框架对比"节

### P3 连贯问题

#### [Section 2 ↔ Section 3]
- 问题:Section 2 用"AI Agent",Section 3 用"智能体",术语不统一
- 建议:统一为"AI Agent"(与用户需求一致)

## 返工计划

1. [P0] Section 2:删除无来源数据或补来源
2. [P1] 新增 Section 4:主流框架对比(委托 section-writer)
3. [P3] 全文术语统一:全文替换"智能体"→"AI Agent"
```

## E. Step 2 详细:Rework 局部返工

### 返工原则

```
1. 优先局部修改:只改有问题的节,不重写全文
2. 按严重程度排序:P0 → P1 → P2 → P3 → P4
3. 每条问题标注位置 + 修改建议,不模糊
4. 修改后重新 Review 受影响节段(不是全文重审)
5. 返工轮次上限:2 轮(仍不通过则标注遗留问题继续)
```

### 返工执行方式

按问题类型选择不同处理方式:

| 问题类型 | 处理方式 | 执行者 |
|---|---|---|
| P0 事实错误(单点) | 直接 edit_file 修正 | 主 Agent |
| P1 需求缺失(整节缺) | task(section-writer) 补写 | section-writer 子 agent |
| P2 大纲偏离(整节跑题) | task(section-writer) 重写 | section-writer 子 agent |
| P3 连贯问题(跨节) | edit_file 统一术语/数据 | 主 Agent |
| P4 完整性(占位符) | edit_file 补全或标注 | 主 Agent |

### 返工后重新 Review

```
1. 返工完成后,只对受影响的节段重新执行 Step 1 的 5 维度审查
2. 不重审未修改的节(节省成本)
3. 更新 /tmp/review_report.md,追加"返工记录":
   ## 返工记录
   ### 第 1 轮返工
   - 修正:Section 2 删除无来源数据
   - 新增:Section 4 主流框架对比
   - 统一:全文术语"AI Agent"
   ### 重新 Review 结论
   - Section 2:✅ 通过
   - Section 4:✅ 通过
   - 全文连贯性:✅ 通过
4. 若仍存在 P0/P1/P2 → 第 2 轮返工(最多 2 轮)
5. 2 轮后仍有问题 → 标注遗留问题,继续进入 HTML 阶段
```

## F. HITL 确认(可选)

返工完成后,若存在以下情况,展示 Review 报告给用户:

```
- 存在 P0/P1 问题且 2 轮返工未完全解决
- 用户原始需求有模糊点(Review 时发现需求理解可能偏差)
- 关键数据无法找到可靠来源

展示内容:
- /tmp/review_report.md 摘要
- 遗留问题清单
- 建议处理方式(继续/补检/调整需求)

用户确认后进入 HTML 制作阶段。
```

若无上述情况,Review 通过后直接进入 HTML 制作(Phase 2.5),无需额外 HITL。

## G. 使用指引(给主 Agent)

```
1. 逐节撰写完成(全部 /tmp/sections/*.md 落盘)后,读取本 SKILL.md
2. 执行 Step 1 Review:
   a. read_file /tmp/outline.md 获取大纲
   b. read_file /tmp/sections/*.md 获取各节内容
   c. 回顾用户原始需求(从会话上下文或 /tmp/research_request.md)
   d. 按 5 维度逐节审查
   e. 生成问题清单,按严重程度分级
   f. replace_file /tmp/review_report.md
3. 判断返工决策:
   - 全部通过 → 跳过 Rework,进入 HTML 制作
   - 存在 P0/P1/P2 → 进入 Step 2 Rework
   - 仅 P5 → 跳过 Rework,在 HTML 阶段顺手修
4. 执行 Step 2 Rework(如需要):
   a. 按问题清单制定返工计划
   b. 按问题类型选择处理方式(edit_file / task(section-writer))
   c. 执行修改
   d. 重新 Review 受影响节段
   e. 用 replace_file 更新 /tmp/review_report.md
5. Review 通过后 → 进入 HTML 制作阶段(读 md-to-pdf SKILL.md)
```

## H. 与其他 skill 的协作

| 上游 | 下游 |
|---|---|
| section-writer(逐节撰写) → /tmp/sections/*.md | Review 通过 → md-to-pdf(HTML 制作 + PDF 渲染) |
| outline-planner(大纲规划) → /tmp/outline.md | 返工时 → section-writer(补写/重写节) |

典型链路:section-writer 落盘 → 本 skill Review → 返工(如需) → md-to-pdf 渲染。
