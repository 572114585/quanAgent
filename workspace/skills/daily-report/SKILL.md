---
name: daily-report
description: "生成结构化的新闻/资讯日报。当用户要总结某领域的新闻日报（如AI新闻、科技资讯、行业动态）时调用。负责拆维度→委托检索→综合→写大纲→写正文→调 md-to-pdf 渲染的全流程编排。不用于单条资讯查询、非日报格式的文档生成。"
allowed-tools: task read_file inspect_file write_file edit_file replace_file check_research_material execute ask_user_question
---

# Daily Report 日报生成

把用户的一句话需求（如"总结AI新闻日报"）变成排版精良的 PDF 日报。

```
用户需求 ─[拆维度]─► 维度清单 ─[task委托research-agent]─► 多份研究素材
    ─[综合归并]─► 大纲 ─[Checkpoint]─► 正文MD ─[调 md-to-pdf skill]─► PDF日报
```

**核心定位：流程编排 skill**，自己不检索、不渲染，只负责把"拆解→委托→综合→写作→交付"串起来。检索能力由通用 research-agent 子 agent 提供，渲染能力由 md-to-pdf skill 提供。

### 工作流程

### Step 1: 规划维度

用 `write_todos` 拆解日报维度。典型维度（按领域调整，不要生搬）：

- 头条/重大事件
- 产品/模型发布
- 融资/收购
- 论文/技术突破
- 开源项目
- 政策/监管

> 维度数量控制在 3-6 个。太少信息量不够，太多每个维度都浅。

### Step 2: 存档原始需求

```
replace_file(path="/tmp/research_request.md", content="<用户原始需求 + 日期>")
```

### Step 3: 委托检索（用通用 research 子 agent）

对每个维度，用 `task()` 委托给 `research-agent`：

- **一次一个主题**，主题要具体（如"最近一周AI模型发布"而非"AI新闻"）
- 多个独立维度可并行，最多 3 个并发
- 每轮检索不超过 3 次委托

```
task(subagent_type="research-agent", description="检索最近一周AI模型发布动态")
```

> research-agent 按两阶段流程先搜摘要、再抓正文，并把 `## 抓取记录` 全文落盘到
> `/tmp/research/<主题>.md`。返回后先用 `check_research_material(..., depth="brief")`
> 校验，再抽查正文。
> 若某维度信息不足，可换关键词再委托一次，但单维度不超过 2 次委托。

### Step 4: 综合发现

- `read_file` 读取各子 agent 落盘的 `/tmp/research/*.md`
- 去重、归类、统一引用编号 `[1][2][3]`
- 每个唯一 URL 分配一个编号，跨所有素材统一

### Step 5: 写大纲

```
replace_file(path="/tmp/outline.md", content="<日报大纲>")
```

大纲结构参考：

```
# AI 新闻日报 - <日期>

## 头条
<1-2 条重大事件>

## 模型与产品
<发布动态>

## 资本动态
<融资/收购>

## 技术与论文
<突破性进展>

## 开源项目
<值得关注的repo>

## 趋势预测
<基于本期动向的简要展望>

### Sources
<所有引用链接>
```

🛑 **Checkpoint**：把大纲要点展示给用户后，**必须调用 `ask_user_question`** 等待确认，再写正文。若用户要求调整维度或增删条目，回到 Step 1/3 调整。禁止纯文本「请确认」后自行开写。

### Step 6: 写正文

按确认后的大纲用 `replace_file` 写 `/tmp/daily_report.md`：

- 每条新闻带来源引用 `[1]`
- 每个维度 2-5 条，每条 2-3 句概述
- 末尾附 `### Sources` 列出所有链接，格式：`[1] 标题: URL`
- 不要编造没有来源的内容，缺数据用 `[此处需要补充: xxx]` 占位

### Step 7: 渲染 PDF

调用 `md-to-pdf` skill 完成最终渲染：

1. 参考 `md-to-pdf` 的 `references/showcase/lite/sample.html` 单栏范式
2. 日报版式建议：单栏 + 左 1/3 右 2/3 网格（见 md-to-pdf 零件目录 L4），左侧放日期/导航/摘要，右侧放正文
3. 纸张 A4
4. 流程：
   ```
   # 先写 HTML
   replace_file(path="output/daily_report.html", content="<参考md-to-pdf showcase/lite设计的HTML>")
   # 再渲染 PDF
   execute(command="python skills/md-to-pdf/scripts/render_pdf.py --html output/daily_report.html --out output/daily_report.pdf --page-size A4")
   ```

### Step 8: 验证与交付

- `read_file` 回读 `/tmp/research_request.md`，确认覆盖用户全部要求
- 确认 `output/daily_report.pdf` 存在且文件大小 > 0
- 汇报：路径、页数、覆盖的维度

---

## 输出约定

| 类型 | 路径 |
|---|---|
| 最终 PDF | `output/daily_report.pdf` |
| 最终 HTML 中间产物 | `output/daily_report.html` |
| 大纲 | `/tmp/outline.md` |
| 正文 MD | `/tmp/daily_report.md` |
| 研究素材 | `/tmp/research/*.md` |
| 原始需求存档 | `/tmp/research_request.md` |

---

## 适配其他领域

本 skill 不限于 AI 领域。接到"XX行业日报""XX领域资讯汇总"时：

- Step 1 的维度按领域调整（如金融日报可换成：市场行情/政策/个股动态/机构观点/宏观指标）
- Step 3 委托检索时关键词带领域上下文
- 其余流程不变

---

## 与其他 skill 的协作

| 上游 | 下游 |
|---|---|
| `research-agent` 子 agent（检索） → 提供素材落盘到 /tmp/research/ | 本 skill 输出 PDF → 可用 `word-docx` 转为可编辑 Word |
| 用户上传的背景资料（可选） | |

典型链路：用户需求 → 本 skill 编排 → research-agent 检索 → md-to-pdf 渲染 → 交付 PDF。
