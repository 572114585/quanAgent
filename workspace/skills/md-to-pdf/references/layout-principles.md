# Layout Principles — 排版要点(自包含模板)

本文件是 `md-to-pdf` skill 的**排版要点参考**,与 `templates/`(自包含模板)配套:

- **模板**(templates/*.html):结构与风格合一,自带完整 CSS(网格 + 分区 + 配色 + 字体 + `@page`)——回答"长什么样 + 内容怎么组织"
- **本文**:讲模板背后的排版原则(为什么这么布局),供选模板 / 改模板 / 自建模板时参考

> 当用户抱怨"版式不好看"时,先看**模板选对了没**——日报用了论文模板、论文用了日报模板,都会难看。模板定了之后,微调直接改模板的 `<style>`。

---

## 1. 自包含模板原则(核心)

```
内容(MD) ──► 自包含模板(templates/*.html)──► HTML ──► PDF
              ↑ 网格/分区/配色/字体/@page 全在一个文件里
              ↑ 图片位置 + 分页策略
```

每个模板文件包含三部分:
1. **头注释**:定位 + 槽位契约 + 视觉签名
2. **`<meta name="section-map">`**:H2 → slot 映射(JSON)
3. **`<meta name="default-slot">`**:未匹配 H2 的默认去向
4. **`<style>`**:完整 CSS(结构 + 风格,硬编码颜色)
5. **`<body>` 骨架**:用 `{{SLOT}}` 占位

| 改这个 | 怎么改 |
|---|---|
| "信息太挤,想分区" | 换 `--template`,或改模板的 grid |
| "颜色太冷,想暖一点" | 改模板 `<style>` 里的 accent hex |
| "图片太散" | 改模板里 figure 的 margin/对齐 |
| "字号太小" | 改模板 `<style>` 的 `--font-body` 或 body font-size |
| "每章都另起一页太浪费纸" | 改模板的 `break-before: page` |

**铁律**:模板内 CSS 硬编码颜色,不用 `var(--color-*)` 外部变量;脚本只做 H2→slot 路由 + `{{SLOT}}` 替换,不注入任何 CSS。这让每个模板都是**自洽的可预览单元**——浏览器直接打开模板文件就能看到效果(填上假数据)。

> 历史背景:早期版本采用"两层分离(结构层模板 × 风格层食谱)",模板用 `var(--color-*)`、食谱注入变量。实践中发现范式不兼容导致"参考没生效",且两层耦合调试困难。现已统一为自包含单层。

---

## 2. 通用排版要点(所有文档类型)

### 2.1 视觉层级——眯眼测试

打印一张,眯眼看到的是**色块分布**,不是文字。健康的层级:
- H1 是最深的色块,占视觉权重 30%
- 正文是中等密度灰块
- 页眉页脚是浅灰细线

不健康的层级(常见 AI slop):
- 所有标题一样大 → 没有层级
- 到处是粗体 → 粗体失效
- 多色块平铺 → 没有焦点

### 2.2 信息密度——纸面利用率

| 文档类型 | 推荐留白率 | 页边距 | 行高 |
|---|---|---|---|
| 日报(1-2 页) | 25-30% | 18-20mm | 1.5 |
| 轻量报告(report-lite,3-8 页) | 35-40% | 30-40mm | 1.55 |
| 中密度报告(report-medium,5-15 页) | 30-35% | 22-28mm | 1.6 |
| 学术论文(report-paper,8-12 页) | 25-30% | 20-25mm | 1.5(双栏) |
| 杂志长文 | 40-50% | 20-25mm | 1.7 |

留白不是浪费,是**让眼睛知道在哪里停**。日报信息密度可以高(快速扫读),论文要松(深度阅读),report-lite 大边距是刻意的"稀疏感"。

### 2.3 分页规则——什么必须在一起

| 元素 | 规则 | 为什么 |
|---|---|---|
| H2/H3 标题 | `break-after: avoid` | 标题不能孤悬页底 |
| 标题 + 首段 | `break-before: avoid`(首段) | 标题与首段分离读起来断裂 |
| figure/table | `break-inside: avoid` | 图表跨页=无法阅读 |
| 代码块(<40 行) | `break-inside: avoid` | 代码跨页难追行号 |
| 引用块 | `break-inside: avoid` | 引用是语义单元 |
| 长表 / 长代码 | `break-inside: auto` + 重复表头 | 允许分页,但每页要有表头 |

### 2.4 图片位置策略——图是内容,不是装饰

**反模式**(常见 AI 错误):
- 把图片当 section 分隔符,插在两个 H2 之间"美观"
- 所有图片居中堆在文档末尾
- 图片比文字大,喧宾夺主

**正确策略**:
1. **就近原则**:图片紧邻引用它的段落(论文里 "如图 1 所示" 后面紧跟 figure)
2. **尺寸分级**:
   - 关键结果图(论文 results):占栏宽 100%,带图注
   - 辅助说明图(日报 details):占栏宽 60-80%,带边框
   - 截图(操作演示):等比缩放到栏宽,不裁剪
3. **图注必须有**:图 N · 简短描述。图注是内容的一部分,帮助读者不读正文也能理解图
4. **不裁剪、不变形**:`max-width: 100%; height: auto` 是底线

---

## 3. 日报排版要点(daily-report 模板)

### 3.1 信息架构

日报的本质是**双向沟通工具**:向上汇报进展,向下记录问题。所以信息架构要回答 4 个问题,顺序固定:
1. **今天做了什么?** → 今日进展(简短,列表)
2. **明天要做什么?** → 明日计划(简短,列表)
3. **具体怎么做的?** → 详细工作(长文本,可含图)
4. **有什么挡路?** → 风险 + 需要支持(短)

### 3.2 网格选择——左 1/3 右 2/3

为什么不是 1:1 对称?
- 左栏放"短信息列表"(进展/计划),信息密度高,窄栏够用
- 右栏放"长文本+图"(详细工作),需要宽栏容纳图片和段落
- 1:2 比例让右栏成为视觉重心,**对应"详细工作才是日报的实质内容"**

### 3.3 顶部信息栏——一行三要素

`日期 · 作者 · 项目` 必须在顶部,用 `--font-small` 字号,作为**元信息**而非内容。不要让日期占 H1 级别——日期是定位锚,不是标题。

### 3.4 摘要 callout——整行浅底

摘要是一页日报的"TL;DR",用浅底 + 左侧 accent 色条让它从正文中跳出来。但**不要用深底反白**——日报是工作文档,不是营销单页。

### 3.5 图片策略

日报里图通常少(0-3 张),多是**截图/示意**。处理:
- 嵌入"详细工作"区(右栏),不单独成章
- 加细边框(`0.5pt hairline`),让截图边界清晰
- 不强制图注——日报图多为"看一下这个现象",无需"图 N"编号

---

## 4. 报告模板族排版要点(report-lite / report-medium / report-paper)

三个报告模板共享同一套槽位契约(`TITLE / AUTHORS / AFFIL / ABSTRACT / BODY / REFERENCES / EXTRA`),medium 多 `SUBTITLE / DATE`。差异在**密度、字体、栏数、表格风格**。

### 4.1 选哪个报告模板

| 模板 | 适合 | 视觉签名 |
|---|---|---|
| `report-lite` | 单篇阅读笔记 / 简短技术备忘 / 1-3 节稀疏文档 | 蓝 accent #2563EB、无衬线、大边距 40mm/30mm、单栏 |
| `report-medium` | 正式技术评审 / 跨团队提案 / 月度总结 | 琥珀 #D97706、Georgia 衬线正文、章节自动编号、@page 页眉标题+页脚日期 |
| `report-paper` | CVPR/NeurIPS 风学术论文 / 图表密集研究 | 双栏、booktabs 三线表、纯黑无彩、摘要上下黑线、紧凑边距 |

选型决策树:
- 页数 < 5 且节少 → `report-lite`
- 需要页眉页脚 + 章节编号 + 正式感 → `report-medium`
- 学术 / 双栏 / 图表多 → `report-paper`

### 4.2 摘要区——三个模板的差异

- **report-lite**:摘要紧贴标题下方,无 callout 包裹,简洁
- **report-medium**:用 `.note-box` 浅底框包裹摘要,左侧琥珀色条,隐藏路由进来的冗余 H2(`.note-box > h2 { display: none }`)
- **report-paper**:摘要上下双黑线分隔,跨双栏居中,标题用 small-caps,隐藏路由进来的冗余 H2(`.abstract h2 { display: none }`)

> **隐藏冗余 H2 的原因**:section-map 把"摘要"H2 块路由到 `{{ABSTRACT}}`,但模板自带"摘要"标题区。若不隐藏,会出现两个"摘要"标题。模板用 `display: none` 隐藏路由进来的 H2,保留模板自有的视觉化标题。

### 4.3 章节编号——report-medium 的 counter

report-medium 用 CSS counter 自动编号章节:
```css
.body { counter-reset: h2counter; }
.body h2::before {
  counter-increment: h2counter;
  content: counter(h2counter) ". ";
  color: var(--accent);
}
```
这让"1. 引言 / 2. 方法 / 3. 实验"自动生成,无需 MD 里手写编号。report-lite / report-paper 不编号(论文用传统 IMRaD 无序号标题)。

### 4.4 表格风格——report-paper 的 booktabs 三线表

学术表格的标准是 **booktabs 三线表**:只有顶底两条粗线 + 表头下一条细线,**无竖线**。这是 Tufte 的 data-ink 原则:墨水只用来承载数据,不画装饰线。

```css
table { border-top: 2pt solid #000; border-bottom: 2pt solid #000; }
thead { border-bottom: 0.5pt solid #000; }
th, td { border: none; }  /* 无竖线、无横线 */
```

report-lite / report-medium 用常规细线表格(0.5pt hairline 全框),适合工程文档。**不要**把 booktabs 用到非学术模板——风格不匹配。

### 4.5 双栏布局——report-paper 的 column-count

```css
.paper-body { column-count: 2; column-gap: 6mm; }
.paper-body h2 { break-after: avoid; column-span: none; }
.references { column-span: all; }  /* 参考文献跨双栏 */
```

注意:`column-count` 在 Playwright/Chromium 下稳定,但**图 表 代码块**要小心跨栏断裂——给它们加 `break-inside: avoid`。长表允许 `break-inside: auto`。

### 4.6 参考文献——悬挂缩进

三个报告模板的参考文献都用**悬挂缩进**:第一行顶格,后续行缩进。这让多条引用的边界清晰。字号 0.9em,行高 1.5(比正文紧),表示"这是元信息不是正文"。

report-medium 的 `{{DATE}}` 占位会进入 `@page` 页脚右下,需要脚本在整个模板(含 `<style>`)上做替换——这是 `md_to_html.py` 的 `fill_template_slots` 在全模板范围替换的原因。

### 4.7 图片策略(报告族通用)

- **就近**:图紧邻引用段,不堆到章节末
- **编号**:report-paper 自动 "图 N"(CSS counter);report-lite/medium 不强制编号
- **图注**:图下方,9pt,居中,描述图在说什么
- **尺寸**:关键结果图占栏宽 100%,流程图/示意图可缩到 70-80% 居中
- **边框**:加 `0.5pt hairline` 细边框,让图与背景分离(白底图尤其需要)
- **双栏注意**:report-paper 里图默认在单栏内,不要 `column-span: all`(除非真的是跨栏大图)

---

## 5. 自定义模板要点

当 4 个内置模板都不合适时(如周报、月报、产品手册),参考以下要点自建。新模板放 `templates/<name>.html`,命名用 kebab-case。

### 5.1 模板文件结构

```html
<!-- 1. 头注释:定位 + 槽位契约 + 视觉签名 -->
<!-- 2. <meta name="section-map">:H2 → slot 映射(JSON) -->
<!-- 3. <meta name="default-slot">:未匹配 H2 的默认去向 -->
<!-- 4. <style>:完整 CSS(结构 + 风格,硬编码颜色) -->
<!-- 5. <body>:结构骨架,用 {{SLOT}} 占位 -->
```

### 5.2 槽位命名

- 用大写 + 下划线:`{{PROGRESS}}`、`{{PAPER_TITLE}}`
- 兜底槽位必须有:`{{EXTRA}}` 或 `{{BODY}}` 接收未匹配的章节(用 `<meta name="default-slot">` 声明)
- 元信息槽位:`{{TITLE}}`、`{{AUTHORS}}`、`{{AFFIL}}`、`{{DATE}}`、`{{SUBTITLE}}` 来自 CLI 参数
- 模板特有元信息:`{{REPORT_TITLE}}`、`{{REPORT_META}}`(日报用)

### 5.3 section-map 设计

- key 是正则 alternation:`"今日进展|今日工作|完成事项"`
- 优先列口语化变体,用户 MD 标题不标准也能命中
- value 是槽位名(大写)
- 三个报告模板的 section-map 一致:`"摘要|abstract|简介"` → ABSTRACT,`"参考文献|references|引用|文献|works cited"` → REFERENCES

### 5.4 自包含 CSS 自检清单

- [ ] 所有颜色硬编码(如 `#0071E3`),不用 `var(--color-*)` 外部变量
- [ ] `@page` 定义了 size + margin + 页眉页脚(可选)
- [ ] `break-before/after/inside` 都设了(标题/图表/代码块)
- [ ] 图片有 `max-width: 100%; height: auto; break-inside: avoid`
- [ ] 至少一个兜底区域(`{{EXTRA}}` 或 `{{BODY}}`)
- [ ] 首页 H1 用 `break-before: avoid` 覆盖默认强制分页(否则首页空白)
- [ ] 模板内 `{{DATE}}` / `{{TITLE}}` 等元信息占位可进 `@page` 页眉页脚(脚本在全模板范围替换)
- [ ] 路由进来的冗余 H2 用 `display: none` 隐藏(若模板自带该区标题)

---

## 6. 常见版式问题诊断

| 症状 | 根因 | 修法 |
|---|---|---|
| "看起来像 AI 生成的报告" | 用了 Inter/Roboto 当正文 + 紫蓝渐变 | 换 `report-medium`(Georgia 衬线)或 `report-paper` |
| "内容堆一坨,没有分区" | 没用结构模板,默认 generic 单列流式 | 加 `--template daily-report` 或 `--template report-medium` |
| "图片乱七八糟" | 图片没就近,堆在末尾 | 改模板,图片嵌入对应 slot;或在 MD 里把图移到引用段后 |
| "每章都另起一页,纸浪费" | 模板里 `break-before: page` 滥用 | 改成 `break-before: auto`,只在 H1 分页 |
| "表格跨页断了读不了" | 没设 `break-inside: avoid` 或表太长 | 短表加 avoid;长表加 `thead { display: table-header-group }` |
| "颜色花,不专业" | 模板里引入了多个 rogue hue | 检查模板 `<style>` 所有 hex,accent 色只用一处 |
| "日报像论文,太正式" | 把 report-paper 用到了日报上 | 换 `--template daily-report` |
| "论文像日报,没仪式感" | 把 daily-report 用到了论文上 | 换 `--template report-paper` |
| "摘要标题重复出现两次" | 路由进来的 H2 没隐藏 | 模板加 `.abstract h2 { display: none }` 或 `.note-box > h2 { display: none }` |
| "页脚日期没显示" | `{{DATE}}` 在 `@page` 规则里但脚本没替换到 | 确认 `fill_template_slots` 在全模板(含 `<style>`)替换,非仅 body |
