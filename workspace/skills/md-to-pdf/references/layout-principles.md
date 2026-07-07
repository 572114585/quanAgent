# Layout Principles — 排版要点(LLM 自由设计参考)

本文件是 `md-to-pdf` skill 的**排版要点参考**,与 `references/showcase/`(真实渲染示例)和 `references/component-catalog.md`(零件目录)配套:

- **showcase**(`references/showcase/{lite,medium,paper}/sample.html`):三套真实渲染示例,CSS 全 inline,浏览器直接打开看效果——回答"长什么样"
- **零件目录**(`references/component-catalog.md`):11 类零件(布局/标题/摘要/代码/表格/callout/页眉页脚/数学/图/参考文献/列表),每类多变体 + 跨模板组合示例——回答"组件怎么拼"
- **本文**:讲排版背后的原则(为什么这么布局),供 LLM 自由设计 HTML 时参考

> 当用户抱怨"版式不好看"时,先看**showcase 范式选对了没**——日报用了论文范式、论文用了日报范式,都会难看。范式定了之后,微调直接改 `output/custom.html` 的 `<style>`。

> 历史背景:早期版本采用"4 个自包含模板 + md_to_html.py 脚本路由 slot"模式,LLM 选模板时看不到渲染效果、无法跨模板借鉴组件,导致"模板没参考价值"。现重构为**单一自由设计模式**:删掉 templates/ 目录和 md_to_html.py 路由脚本,只保留 showcase 真实示例 + 零件目录作为参考素材,由 LLM `write_file output/custom.html` 自由设计内嵌完整 CSS 的自包含 HTML。本文档已对齐新模型,不再描述 templates/、section-map、fill_template_slots、md_to_html.py 等已删除的旧机制。

---

## 1. 自由设计原则(核心)

```
内容(MD) ──► LLM 参考 showcase + 零件目录 ──► write_file output/custom.html(自包含)──► PDF
                  ↑ 网格/分区/配色/字体/@page 全由 LLM 在 <style> 里硬编码
                  ↑ 图片位置 + 分页策略
```

LLM 设计 HTML 时的产出要求:

1. **参考 showcase 选范式**:翻 `references/showcase/{lite,medium,paper}/sample.html` 选整体布局风格(浏览器打开看效果)
2. **从零件目录挑组件**:读 `references/component-catalog.md`,按 11 类挑组件,可跨模板组合(如 paper 双栏 + medium 琥珀 callout)
3. **`write_file output/custom.html`**:产出自包含 HTML(CSS 全 inline 进 `<style>`,不依赖外部文件),内容来自 MD,版式来自组件选型

产出的 HTML 必须满足:
- **自包含**:CSS 全 inline,浏览器直接打开能看完整效果
- **配色硬编码**:不用 `var()` 外部变量,颜色直接写 hex(如 `#D97706`),让 HTML 是自洽的可预览单元
- **兜底**:所有 MD 内容都有去处,不丢章节

| 改这个 | 怎么改 |
|---|---|
| "信息太挤,想分区" | 换 showcase 范式,或改 custom.html 的 grid/column-count |
| "颜色太冷,想暖一点" | 改 custom.html `<style>` 里的 accent hex |
| "图片太散" | 改 custom.html 里 figure 的 margin/对齐 |
| "字号太小" | 改 custom.html `<style>` 的 body font-size |
| "每章都另起一页太浪费纸" | 改 custom.html 的 `break-before: page` |

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
| 轻量报告(lite 范式,3-8 页) | 35-40% | 30-40mm | 1.55 |
| 中密度报告(medium 范式,5-15 页) | 30-35% | 22-28mm | 1.6 |
| 学术论文(paper 范式,8-12 页) | 25-30% | 20-25mm | 1.5(双栏) |
| 杂志长文 | 40-50% | 20-25mm | 1.7 |

留白不是浪费,是**让眼睛知道在哪里停**。日报信息密度可以高(快速扫读),论文要松(深度阅读),lite 范式大边距是刻意的"稀疏感"。

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

> **图片控尺寸硬规则**(SKILL.md Step 3 已规定):所有图片必须包在 `<figure>` 里,用 figure 控宽高 + 居中 + 图注。img 加 `max-height` 约束防过高(双栏 220px / 单栏 300px)。详见 SKILL.md "图片处理" 章节。

---

## 3. 日报排版要点

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

> 日报范式参考:`showcase/lite` 的单栏 + 自定义左1/3右2/3 网格(见 `component-catalog.md` L4 布局类)。

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

## 4. 报告范式族排版要点(lite / medium / paper)

三套 showcase 范式共享同一套内容槽位概念(TITLE / AUTHORS / ABSTRACT / BODY / REFERENCES),但由 LLM 在 custom.html 里自由组织,无脚本路由。差异在**密度、字体、栏数、表格风格**。

### 4.1 选哪个范式

| 范式 | 适合 | 视觉签名 | showcase 路径 |
|---|---|---|---|
| `lite` | 单篇阅读笔记 / 简短技术备忘 / 1-3 节稀疏文档 | 蓝 accent #2563EB、无衬线、大边距 40mm/30mm、单栏 | `showcase/lite/sample.html` |
| `medium` | 正式技术评审 / 跨团队提案 / 月度总结 | 琥珀 #D97706、Georgia 衬线正文、章节自动编号、@page 页眉标题+页脚日期 | `showcase/medium/sample.html` |
| `paper` | CVPR/NeurIPS 风学术论文 / 图表密集研究 | 双栏、booktabs 三线表、纯黑无彩、摘要上下黑线、紧凑边距 | `showcase/paper/sample.html` |

选型决策树:
- 页数 < 5 且节少 → `lite`
- 需要页眉页脚 + 章节编号 + 正式感 → `medium`
- 学术 / 双栏 / 图表多 → `paper`

> 三套 showcase 都是 D4RT 论文示例,题材单一。非学术场景参考价值降低时,LLM 应跨模板组合(如 paper 双栏 + medium 琥珀 callout)或从 component-catalog.md 自由拼装。

### 4.2 摘要区——三个范式的差异

- **lite**:摘要紧贴标题下方,无 callout 包裹,简洁
- **medium**:用 `.note-box` 浅底框包裹摘要,左侧琥珀色条
- **paper**:摘要上下双黑线分隔,跨双栏居中,标题用 small-caps

> **关于"摘要标题重复"**:MD 里可能有 `## 摘要` H2,而 custom.html 的 HTML 骨架里也自带摘要区标题。LLM 设计时应用 CSS 隐藏冗余 H2(如 `.note-box > h2 { display: none }`),保留 HTML 骨架的视觉化标题。这是 LLM 设计决策,不是脚本路由。

### 4.3 章节编号——medium 范式的 counter

medium 范式用 CSS counter 自动编号章节:
```css
.body { counter-reset: h2counter; }
.body h2::before {
  counter-increment: h2counter;
  content: counter(h2counter) ". ";
  color: #D97706;  /* 硬编码琥珀色,不用 var() */
}
```
这让"1. 引言 / 2. 方法 / 3. 实验"自动生成,无需 MD 里手写编号。lite / paper 不编号(论文用传统 IMRaD 无序号标题)。

### 4.4 表格风格——paper 范式的 booktabs 三线表

学术表格的标准是 **booktabs 三线表**:只有顶底两条粗线 + 表头下一条细线,**无竖线**。这是 Tufte 的 data-ink 原则:墨水只用来承载数据,不画装饰线。

```css
table { border-top: 2pt solid #000; border-bottom: 2pt solid #000; }
thead { border-bottom: 0.5pt solid #000; }
th, td { border: none; }  /* 无竖线、无横线 */
```

lite / medium 用常规细线表格(0.5pt hairline 全框),适合工程文档。**不要**把 booktabs 用到非学术范式——风格不匹配。

### 4.5 双栏布局——paper 范式的 column-count

```css
.paper-body { column-count: 2; column-gap: 6mm; }
.paper-body h2 { break-after: avoid; column-span: none; }
.references { column-span: all; }  /* 参考文献跨双栏 */
```

注意:`column-count` 在 Playwright/Chromium 下稳定,但**图 表 代码块**要小心跨栏断裂——给它们加 `break-inside: avoid`。长表允许 `break-inside: auto`。

### 4.6 参考文献——悬挂缩进

三个范式的参考文献都用**悬挂缩进**:第一行顶格,后续行缩进。这让多条引用的边界清晰。字号 0.9em,行高 1.5(比正文紧),表示"这是元信息不是正文"。

> medium 范式若在 `@page` 页脚用日期,LLM 设计 custom.html 时直接把日期写死在 `@page` 规则的 `content` 里(如 `content: "2026-07-07"`),或用 CSS `string-set` 从 DOM 取值。无需脚本替换——custom.html 是自包含的。

### 4.7 图片策略(报告族通用)

- **就近**:图紧邻引用段,不堆到章节末
- **编号**:paper 范式自动 "图 N"(CSS counter);lite/medium 不强制编号
- **图注**:图下方,9pt,居中,描述图在说什么
- **尺寸**:关键结果图占栏宽 100%,流程图/示意图可缩到 70-80% 居中
- **边框**:加 `0.5pt hairline` 细边框,让图与背景分离(白底图尤其需要)
- **双栏注意**:paper 范式里图默认在单栏内,不要 `column-span: all`(除非真的是跨栏大图)

---

## 5. 自定义 HTML 设计要点

当三套 showcase 范式都不合适时(如周报、月报、产品手册),LLM 参考以下要点自由设计 `output/custom.html`。

### 5.1 HTML 文件结构

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>文档标题</title>
<style>
/* 1. @page:size + margin + 页眉页脚 */
/* 2. 完整 CSS:布局 + 配色 + 字体 + 分页规则,颜色全硬编码 */
/* 3. 组件 CSS:从 component-catalog.md 挑的零件,按选型拼接 */
</style>
</head>
<body>
<!-- 4. 结构骨架:标题区 + 摘要区 + 正文 + 参考文献,内容来自 MD -->
</body>
</html>
```

### 5.2 内容组织原则

- **从 MD 解析章节结构**:H1/H2/H3 决定 HTML 的 `<h1>`/`<h2>`/`<h3>` 层级
- **元信息写死或从 MD 取**:标题/作者/日期可从 MD frontmatter 或首行取,也可由 LLM 根据用户需求写死
- **兜底区必须有**:MD 里未明确归类的章节应有默认去向(如正文 body 区),不丢内容
- **跨模板组合**:可混合多套 showcase 的组件(如 paper 双栏 + medium 琥珀 callout),从 component-catalog.md 挑零件

### 5.3 自包含 CSS 自检清单

- [ ] 所有颜色硬编码(如 `#0071E3`),不用 `var(--color-*)` 外部变量
- [ ] `@page` 定义了 size + margin + 页眉页脚(可选)
- [ ] `break-before/after/inside` 都设了(标题/图表/代码块)
- [ ] 图片有 `max-width: 100%; height: auto; break-inside: avoid`,且包在 `<figure>` 里控尺寸
- [ ] 至少一个兜底区域(正文 body 区接收未明确归类的章节)
- [ ] 首页 H1 用 `break-before: avoid` 覆盖默认强制分页(否则首页空白)
- [ ] `@page` 页眉页脚的 `content` 若需日期/标题,直接写死或用 `string-set`,无需脚本替换
- [ ] MD 里的冗余 H2(如"摘要")若与 HTML 骨架自带标题重复,用 `display: none` 隐藏

---

## 6. 常见版式问题诊断

| 症状 | 根因 | 修法 |
|---|---|---|
| "看起来像 AI 生成的报告" | 用了 Inter/Roboto 当正文 + 紫蓝渐变 | 换 `showcase/medium`(Georgia 衬线)或 `showcase/paper` |
| "内容堆一坨,没有分区" | 没用结构化布局,默认单列流式 | 参考 `showcase/lite` 加左1/3右2/3 网格,或 `showcase/medium` 的章节分区 |
| "图片乱七八糟" | 图片没就近,堆在末尾 | 改 custom.html,图片嵌入对应章节;或在 MD 里把图移到引用段后 |
| "每章都另起一页,纸浪费" | custom.html 里 `break-before: page` 滥用 | 改成 `break-before: auto`,只在 H1 分页 |
| "表格跨页断了读不了" | 没设 `break-inside: avoid` 或表太长 | 短表加 avoid;长表加 `thead { display: table-header-group }` |
| "颜色花,不专业" | custom.html 引入了多个 rogue hue | 检查 `<style>` 所有 hex,accent 色只用一处 |
| "日报像论文,太正式" | 把 paper 范式用到了日报上 | 换 `showcase/lite` 范式 |
| "论文像日报,没仪式感" | 把 lite 范式用到了论文上 | 换 `showcase/paper` 范式 |
| "摘要标题重复出现两次" | MD 的 `## 摘要` H2 没隐藏 | custom.html 加 `.abstract h2 { display: none }` 或 `.note-box > h2 { display: none }` |
| "页脚日期没显示" | `@page` 页脚 `content` 没写日期 | 直接在 `@page` 的 `content` 里写死日期,或用 `string-set` 从 DOM 取 |
