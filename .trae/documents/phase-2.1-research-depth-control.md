# Phase 2.1：检索深度调控 — 详细设计

## Summary

让 research_subagent 能根据**文档类型**和**用户意图深度**，以**两阶段（先广度后深度）**方式检索资料；主 Agent 在检索完成后对照策略 Review，不吻合则补检一轮。核心交付：web_search 参数化 + research-strategies skill（两层结构）+ research_subagent 升级 + 主 Agent Review 编排。

## Current State Analysis

### 当前搜索实现（基于代码探索）

| 维度 | 现状 | 问题 |
|---|---|---|
| web_search 参数 | `query, max_results=5, topic="general"` 仅 3 个 | 无深度控制参数 |
| 正文抓取篇数 | `_FETCH_TOP_N=2` 硬编码 | 调用方不可控 |
| 单篇字数上限 | `_MAX_CONTENT_CHARS=4000` 硬编码 | 调用方不可控 |
| Tavily 深度参数 | `search_depth="basic"`, `include_raw_content=False` 硬编码 | 主动关闭以省额度 |
| research_subagent | 纯文字指引（"多角度换关键词""不堆大量结果"） | 无结构化策略，深度靠 LLM 自由判断 |
| 检索后 Review | 无 | 检索质量无保障，可能漏检或浅检 |
| 文档类型区分 | 仅 `topic="general"/"news"` | 无产品介绍/技术调研/数据分析等类型策略 |

### 关键文件

- [tools/web_search.py](file:///d:/project/tools/web_search.py) — web_search 工具，L18-25 硬编码常量，L108-151 工具签名与实现
- [tools/search/base.py](file:///d:/project/tools/search/base.py) — SearchQuery 数据类（L13-19），SearchResult（L22-29，content 字段未使用）
- [tools/search/tavily.py](file:///d:/project/tools/search/tavily.py) — L35-38 硬编码 search_depth/include_raw_content
- [agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) — SYSTEM_PROMPT（L11-24），research_subagent（L27-43）
- [workspace/skills/daily-report/SKILL.md](file:///d:/project/workspace/skills/daily-report/SKILL.md) — 现有 skill 结构参考

## Proposed Changes

### 改动 1：web_search 工具参数化

**文件**：[tools/web_search.py](file:///d:/project/tools/web_search.py)

**What**：把硬编码的 `_FETCH_TOP_N` 和 `_MAX_CONTENT_CHARS` 变成工具可选参数，新增 `search_depth` 参数控制 Tavily provider 行为。

**Why**：research_subagent 需要按策略控制"抓几篇正文""每篇多长"，当前完全无法控制。

**How**：

1. 工具签名改为：
```python
@tool
def web_search(
    query: str,
    max_results: int = 5,
    topic: str = "general",
    fetch_top_n: int = 2,
    max_content_chars: int = 4000,
) -> str:
```
- `fetch_top_n`：抓取正文的篇数，默认 2（保持向后兼容）。传 0 表示不抓正文（广度阶段用）。
- `max_content_chars`：单篇正文字符上限，默认 4000（保持向后兼容）。

2. L137 的 `if idx < _FETCH_TOP_N` 改为 `if idx < fetch_top_n`

3. L101 的 `md[:_MAX_CONTENT_CHARS]` 改为 `md[:max_content_chars]`

4. L19/L23 的模块级常量 `_FETCH_TOP_N` / `_MAX_CONTENT_CHARS` 保留为默认值来源（默认参数引用它们），但不再在逻辑中直接使用。

5. 工具 docstring 更新，说明 `fetch_top_n=0` 用于广度阶段（只看摘要），`fetch_top_n>=3` 用于深度阶段。

**不改的**：
- `_FETCH_TIMEOUT`、`_MAX_FETCH_BYTES` 保持硬编码（安全限制，不应让 LLM 控制）
- provider 层（tavily/brave/serper/duckduckgo）暂不改（见改动 5 的"可选"说明）

---

### 改动 2：新增 research-strategies skill

**文件**：新建 `workspace/skills/research-strategies/SKILL.md`

**What**：两层结构的检索策略手册 — markdown 描述策略意图 + 结构化参数表。research_subagent 和主 Agent 都可查阅。

**Why**：用户选择了"两层结合"方案。research_subagent 读文档理解"该怎么搜"，参数表提供具体数值边界。

**目录结构**：
```
workspace/skills/research-strategies/
├── SKILL.md                          # 入口：策略总览 + 参数表 + 使用指引
└── references/
    └── doc-type-strategies.md        # 4 种文档类型的详细策略
```

**SKILL.md 内容大纲**：

```yaml
---
name: research-strategies
description: "检索策略手册。当需要按文档类型和深度等级调控联网搜索行为时查阅。定义产品介绍/技术调研/新闻日报/数据分析 4 种文档类型的检索策略，以及 brief/standard/in-depth 3 级深度的参数映射。供 research-agent 子 agent 和主 Agent 在检索前读取。"
allowed-tools: read_file
---
```

**主体内容**：

#### A. 深度等级定义（3 级）

| 等级 | 触发条件 | 目标 | 广度阶段参数 | 深度阶段参数 |
|---|---|---|---|---|
| brief（简报） | 用户说"简报""概览""快速了解" 或 文档类型为新闻日报 | 快、浅、覆盖面够即可 | max_results=3, fetch_top_n=0 | fetch_top_n=1, max_content_chars=2000 |
| standard（标准） | 默认，用户未明确说明 | 适中深度 + 适中覆盖 | max_results=5, fetch_top_n=0 | fetch_top_n=2, max_content_chars=4000 |
| in-depth（深度） | 用户说"详细""深入""全面""深度调研" 或 文档类型为技术调研/数据分析 | 慢、深、多源交叉验证 | max_results=8, fetch_top_n=0 | fetch_top_n=4, max_content_chars=8000 |

> **深度判断规则**：
> 1. 用户显式说明（"详细的""简报"）→ 按说明走
> 2. 用户未说明 → 按文档类型默认深度（见下表）
> 3. 文档类型也未确定 → 默认 standard

#### B. 文档类型策略矩阵

| 文档类型 | 默认深度 | 来源优先级 | 关键词策略 | 特殊要求 |
|---|---|---|---|---|
| 产品介绍（product_brief） | standard | 官方资料 > 用户评价 > 竞品对比 | 产品名 + "功能/定价/评测/对比" | 需覆盖：核心功能、定价、优劣势、竞品对比 |
| 技术调研（tech_research） | in-depth | 官方文档 > 论文 > 技术博客 > 营销内容 | 技术名 + "原理/架构/对比/性能/论文" | 需交叉验证（同一结论 ≥2 个独立来源） |
| 新闻日报（news_daily） | brief | 近 7 天一手报道 > 转载 | 领域名 + "最新/发布/动态/2026"（带年份） | topic="news"，时效性 > 深度 |
| 数据分析（data_analysis） | in-depth | 统计报告 > 财报 > 行业数据 > 新闻 | 指标名 + "数据/统计/报告/趋势" | 需结构化数据（表格/数字），每指标 ≥3 独立来源 |

#### C. 两阶段搜索流程

```
阶段 1：广度撒网（breadth）
  - 目标：快速判断"有哪些相关内容"，不抓正文
  - 方法：多关键词（3-5 组），每组 web_search(fetch_top_n=0)
  - 产出：标题+摘要列表，按相关性筛选出 top N 个 URL
  - 判断：哪些 URL 值得深入抓取？

阶段 2：深度钻取（depth）
  - 目标：对阶段 1 筛选出的 URL 抓取全文
  - 方法：web_search(fetch_top_n=N, max_content_chars=M)
    或换更精准的关键词重新搜索并抓全文
  - 产出：带全文正文的结构化素材
```

#### D. 使用指引（给 research_subagent）

```
1. 接到任务后，先判断文档类型和深度等级
   （主 Agent 会在 task() 的 description 里告知，如"深度调研 AI Agent 技术原理"）
2. 读本 SKILL.md 确认对应策略的参数和来源偏好
3. 执行两阶段搜索：
   - 阶段 1：按策略广度参数搜 3-5 组关键词，fetch_top_n=0
   - 筛选相关 URL
   - 阶段 2：按策略深度参数抓取筛选后 URL 的全文
4. 把发现写入 /tmp/research/<主题>.md（含来源、日期、阶段标记）
5. 返回摘要 + 文件路径
```

**references/doc-type-strategies.md**：对每种文档类型展开详细策略（典型维度、关键词模板、来源黑白名单、Review 检查清单），供需要时深入查阅。

---

### 改动 3：research_subagent 升级

**文件**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) L27-43

**What**：重写 research_subagent 的 system_prompt，支持两阶段搜索 + 策略读取。

**Why**：当前 system_prompt 是单阶段无策略的，需要让子 agent 按策略执行两阶段检索。

**How**：

```python
research_subagent = {
    "name": "research-agent",
    "description": (
        "委托研究子任务。每次只给一个明确的主题/问题，"
        "并在 description 中注明文档类型和深度等级"
        "（如'tech_research in-depth: 调研 AI Agent 技术原理'）。"
        "子 agent 会按 research-strategies skill 的策略执行两阶段检索，"
        "把发现写到 /tmp/research/<topic>.md，返回摘要 + 文件路径。"
    ),
    "system_prompt": (
        "你是通用研究助手。接到任务后：\n"
        "1. 先调 get_current_time 确认当前日期\n"
        "2. 从 task description 解析文档类型和深度等级（如 tech_research in-depth）\n"
        "3. 读 skills/research-strategies/SKILL.md 确认对应策略\n"
        "4. 执行两阶段搜索：\n"
        "   阶段1 广度：按策略广度参数，换 3-5 组关键词搜索，fetch_top_n=0（只看标题+摘要），"
        "筛选出最相关的 URL\n"
        "   阶段2 深度：按策略深度参数，对筛选后的 URL 抓取全文（fetch_top_n 和 max_content_chars 按策略表）\n"
        "5. 把发现用 write_file 写入 /tmp/research/<主题>.md（含来源、日期、标注广度/深度阶段）\n"
        "6. 返回简短摘要 + 文件路径\n"
        "原则：\n"
        "- 来源优先级按策略表（如技术调研优先官方文档/论文）\n"
        "- 新闻类用 topic=\"news\"，query 带年份\n"
        "- 不要在上下文里堆大量结果，筛选后只留相关的\n"
        "- 本地知识库（产品文档/内部资料）用 kb_search，外部信息用 web_search\n"
    ),
    "tools": [get_current_time, web_search, kb_search, kb_add_document],
}
```

**关键变化**：
- description 要求主 Agent 在 task() 时注明"文档类型 + 深度等级"
- system_prompt 明确两阶段流程
- 引导子 agent 读 research-strategies SKILL.md
- web_search 调用时按策略传 fetch_top_n / max_content_chars

---

### 改动 4：主 Agent Review 编排

**文件**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) L11-24（SYSTEM_PROMPT）

**What**：在 SYSTEM_PROMPT 的"通用编排原则"中新增"检索 Review"原则。

**Why**：用户要求"检索完一轮了之后，review一轮，查看内容是否与策略所吻合，若不吻合则再检索多一轮"。主 Agent 负责审查。

**How**：在现有 SYSTEM_PROMPT 的原则列表中追加：

```python
SYSTEM_PROMPT = """你是权哥的助手，你叫做小权，你的任务是帮助权哥完成各种任务。

## 文件输出目录约定（必须遵守）
...（保持不变）...

## 通用编排原则
- **复杂任务先规划**：...（保持不变）...
- **检索委托给子 agent**：...（保持不变）...
- **本地知识库优先**：...（保持不变）...
- **按 Skill 执行**：...（保持不变）...
- **关键节点停下确认**：...（保持不变）...
- **检索深度调控**：委托检索前，先判断文档类型和深度等级（brief/standard/in-depth）。
  用户显式说明（"详细的""简报"）→ 按说明走；未说明 → 按文档类型默认（技术调研/数据分析=in-depth，
  产品介绍=standard，新闻日报=brief）。在 task() 的 description 中注明，如
  "tech_research in-depth: 调研 AI Agent 技术原理"。读 skills/research-strategies/SKILL.md 了解策略细节。
- **检索结果 Review**：research-agent 返回后，对照策略审查检索结果：
  · 覆盖度：策略要求的关键词/维度都搜了吗？
  · 相关性：结果和主题相关吗？有跑偏吗？
  · 来源质量：权威来源占比够吗？（技术调研要有官方文档/论文，不能全是营销文）
  · 数量：结果条数达到策略要求了吗？
  不吻合 → 再派一轮 task()，在 description 中指明补充方向（如"补充检索 XX 方向，已有 YY 不用重复"）。
  最多补检 2 轮，仍不够则在结果中标注"信息不足"并继续。
"""
```

---

### 改动 5（可选，低优先级）：SearchQuery 扩展 Tavily 深度

**文件**：[tools/search/base.py](file:///d:/project/tools/search/base.py)、[tools/search/tavily.py](file:///d:/project/tools/search/tavily.py)

**What**：SearchQuery 加 `search_depth` 字段，Tavily provider 在 in-depth 等级时启用 `search_depth="advanced"` 和 `include_raw_content=True`。

**Why**：当前 Tavily 的 advanced 模式和 raw_content 被硬编码关闭。in-depth 等级时启用可提升深度阶段质量。但会消耗更多 API 额度。

**Why optional**：改动 1-4 已经通过 httpx 抓取实现了深度控制，不依赖 Tavily 原生深度。这个改动是锦上添花，可后续再做。

**How（如果做）**：
1. `SearchQuery` 加 `search_depth: str = "basic"` 字段
2. `web_search` 工具加 `search_depth` 参数透传
3. `tavily.py` L35 改为 `"search_depth": query.search_depth`
4. `tavily.py` L38 改为 `"include_raw_content": query.search_depth == "advanced"`

**建议**：Phase 2.1 先不做，保持 Tavily 省额度策略。等验证 httpx 抓取的深度够用后再决定。

---

## Assumptions & Decisions

1. **深度等级 3 级**（brief/standard/in-depth）— 覆盖"简报""默认""详细报告"三种用户意图，不多不少
2. **文档类型 4 种**（product_brief/tech_research/news_daily/data_analysis）— 与 README_ARCHITECTURE 第 7.2.1 节一致
3. **两阶段搜索**（广度→深度）— 参考 GPT Researcher 模式，广度阶段 `fetch_top_n=0` 只看摘要快速筛选，深度阶段抓全文
4. **主 Agent Review**（非子 agent 自审）— 主 Agent 有全局视角，能看到用户完整需求和策略
5. **最多补检 2 轮**— 避免无限循环，仍不够则标注"信息不足"继续
6. **策略放 skills 目录**（非 tools/）— 策略是"可复用流程/示例"，符合 README_ARCHITECTURE 第 5 节对 Skills 的定义
7. **web_search 加参数而非新建工具**— 保持向后兼容，默认值与当前硬编码一致
8. **Tavily advanced 模式暂不启用**（改动 5 标为可选）— 优先用 httpx 抓取，省 API 额度
9. **research_subagent 仍用现有 task() 机制**— 不改 DeepAgents 的 subagent 调用方式，只改 system_prompt

## Verification Steps

### 验证改动 1（web_search 参数化）

1. 不传新参数，行为与原来一致：
   ```
   web_search(query="AI Agent")  # fetch_top_n=2, max_content_chars=4000（默认）
   ```
   预期：抓前 2 篇正文，每篇 4000 字截断，与改动前完全一致。

2. 传 `fetch_top_n=0`，不抓正文（广度阶段）：
   ```
   web_search(query="AI Agent", fetch_top_n=0)
   ```
   预期：只返回标题+摘要，无"## 正文"段落。

3. 传 `fetch_top_n=4, max_content_chars=8000`，深度抓取（深度阶段）：
   ```
   web_search(query="AI Agent 技术原理", fetch_top_n=4, max_content_chars=8000)
   ```
   预期：前 4 篇有正文，每篇最多 8000 字。

### 验证改动 2（research-strategies skill）

1. `read_file skills/research-strategies/SKILL.md` 能正常读取
2. 文档类型策略矩阵 4 种类型 × 3 级深度参数完整
3. 两阶段搜索流程描述清晰

### 验证改动 3（research_subagent 升级）

1. 主 Agent 调 `task(subagent_type="research-agent", description="tech_research in-depth: 调研 AI Agent 技术原理")`
2. 子 agent 应：
   - 读 research-strategies/SKILL.md
   - 阶段 1：搜 3-5 组关键词，fetch_top_n=0
   - 阶段 2：对筛选 URL 抓全文，fetch_top_n=4, max_content_chars=8000
   - 写入 /tmp/research/<主题>.md
3. 返回摘要 + 文件路径

### 验证改动 4（主 Agent Review）

1. 模拟检索不足场景：子 agent 只搜了 1 组关键词返回
2. 主 Agent 应识别"覆盖度不足"，再派一轮 task 指明补充方向
3. 最多 2 轮补检后继续

### 端到端验证

对 LLM 说："帮我做一份详细的 AI Agent 行业技术调研报告"：
1. 主 Agent 判断：doc_type=tech_research, depth=in-depth
2. task() 委托 research-agent，description 含 "tech_research in-depth"
3. 子 agent 按策略两阶段检索
4. 主 Agent Review：检查覆盖度/来源质量/数量
5. 不够则补检，够则进入下一阶段（大纲规划）

---

## 不做的事（明确边界）

- ❌ 不改 provider 层（tavily/brave/serper/duckduckgo）的 search() 实现 — 改动 5 标为可选，Phase 2.1 先不做
- ❌ 不新增独立 review 工具 — Review 由主 Agent 用 LLM 判断，不做成 tool
- ❌ 不改 DeepAgents 的 task()/subagent 机制 — 只改 system_prompt
- ❌ 不改 kb_tool.py — 知识库检索的深度调控（top_k/MAX_PER_HIT）暂不在本 Phase 范围
- ❌ 不做检索结果的结构化存储（数据库）— 本 Phase 沿用 /tmp/research/*.md 落盘方式
- ❌ 不做并行搜索编排 — research_subagent 内部串行执行两阶段，多维度并行由主 Agent 用多个 task() 实现
