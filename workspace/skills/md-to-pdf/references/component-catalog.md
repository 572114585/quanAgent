# Component Catalog — 组件零件目录（模式 B 自由设计）

本文件是 `md-to-pdf` skill **模式 B（自由设计主车道）** 的核心参考。

**用法**：模式 B 下，把 MD 转 PDF 时不在内置模板里挑，而是由 LLM 自由拼装一份 `output/custom.html`。流程是：
1. 先翻 `references/showcase/{lite,medium,paper}/sample.html`，选定**整体范式**（轻量稀疏 / 正式衬线 / 学术双栏）。
2. 再从**本目录**按类别挑零件（布局、标题、代码、表格……），像搭积木一样组装。
3. 颜色 / 字体 / 边距按场景微调（硬编码 hex，不用 `var()`）。
4. `write_file` 写到 `output/custom.html`，交给 `render_pdf.py` 出 PDF。

> 三套源模板的视觉签名：
> - **lite**：蓝 accent `#2563EB`、无衬线、大边距 40mm/30mm、单栏稀疏
> - **medium**：琥珀 accent `#D97706`、Georgia 衬线正文、章节自动编号、`.note-box` 摘要、深色代码块带文件名标签
> - **paper**：双栏、booktabs 三线表、纯黑无彩、摘要上下黑线

每个零件标注【来自：lite/medium/paper】，CSS 片段直接从源模板提取（精简注释，保留视觉关键属性）。

---

## 1. 布局类（Layout）

### L1 单栏大边距【来自：lite】
适用：阅读笔记 / 简短技术备忘 / 1-3 节稀疏文档。刻意"稀疏感"，让眼睛知道在哪里停。

```css
@page { size: A4; margin: 40mm 30mm; }
body {
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  max-width: 680px; margin: 0 auto; padding: 60px 40px;
}
@media print { body { max-width: none; padding: 0; } }
```

### L2 单栏标准【来自：medium】
适用：正式技术评审 / 跨团队提案 / 月度总结。max-width 720px 居中，正文 Georgia 衬线。

```css
@page { size: A4; margin: 30mm 25mm; }
body {
  font-family: Georgia, "Times New Roman", "Noto Serif", serif;
  font-size: 12px; line-height: 1.6; color: #333;
}
main { max-width: 720px; margin: 0 auto; padding: 60px 0; }
@media print { main { padding: 0; max-width: none; } body { font-size: 9pt; } }
```

### L3 双栏【来自：paper】
适用：学术论文 / 图表密集研究。`column-count:2`，gap 24px。注意图表代码块要加 `break-inside:avoid` 防跨栏断裂。

```css
@page { size: A4; margin: 25mm 20mm; }
.two-col {
  column-count: 2; column-gap: 24px;
  -webkit-column-count: 2; -webkit-column-gap: 24px;
}
/* 跨栏元素：标题区 / 摘要 / 参考文献 / 大图 */
.full-width { column-span: all; -webkit-column-span: all; }
```

### L4 左 1/3 右 2/3 网格【来自：daily-report，由 layout-principles 推导】
适用：日报 / 周报。左栏放短信息列表（进展/计划），右栏放长文本+图（详细工作）。1:2 比例让右栏成为视觉重心。

```css
.report-main {
  display: grid;
  grid-template-columns: 1fr 2fr;
  grid-template-rows: auto auto;
  gap: 8mm 8mm;
}
.report-progress { grid-column: 1; grid-row: 1; break-inside: avoid; }
.report-plan     { grid-column: 1; grid-row: 2; break-inside: avoid; }
.report-details  { grid-column: 2; grid-row: 1 / span 2; break-inside: auto; } /* 长内容允许分页 */
```

**组合建议**：双栏正文（L3）想加一个跨栏标题区时，给标题容器套 `.full-width { column-span: all }` 放在 `.two-col` **之前**（标题区在双栏流之外，再进入双栏）。同理摘要、参考文献也用 `column-span: all` 单独跨栏。日报网格 L4 不要和 column-count 混用——网格是二维，column 是一维流，叠在一起会乱。

---

## 2. 标题区类（Headings）

### H1 居中带蓝色下边框【来自：lite】
```css
h1 {
  font-size: 28px; text-align: center; font-weight: 700; color: #1A1A1A;
  border-bottom: 2px solid #2563EB;
  padding-bottom: 0.6em; margin-bottom: 1.5em;
}
```

### H1 居中 + 页眉文档标题【来自：medium】
H1 本身居中（无装饰线），文档标题通过 `@page` 的 `@top-center` 进每页页眉。要做"标题随 H1 动态变化"，用 `string-set` 把 H1 文本喂给页眉：

```css
h1 { font-size: 24px; text-align: center; color: #111827; margin-bottom: 0.3em; }

/* 方式一：硬编码（medium 源模板现状） */
@page { @top-center { content: "文档标题"; font-size: 8pt; color: #9CA3AF; text-transform: uppercase; letter-spacing: 1px; } }

/* 方式二：string-set 动态（推荐，让 H1 文本进页眉） */
h1 { string-set: doctitle content(); }
@page { @top-center { content: string(doctitle); font-size: 8pt; color: #9CA3AF; } }
```

### H1 跨双栏居中【来自：paper】
标题块整体 `column-span: all`，放在双栏流之外。

```css
.title-block { text-align: center; margin-bottom: 12px; column-span: all; -webkit-column-span: all; }
.title-block h1 {
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  font-size: 20px; font-weight: 700; line-height: 1.3; color: #000; margin-bottom: 8px;
}
```

### H2 蓝色左边框【来自：lite】
```css
h2 {
  font-size: 20px; font-weight: 700; color: #1A1A1A;
  border-left: 4px solid #2563EB; padding-left: 12px;
  margin-top: 2em; margin-bottom: 1em;
}
```

### H2 自动编号 counter + 琥珀色【来自：medium】
"1. 引言 / 2. 方法"自动生成，MD 里不用手写编号。counter 挂在 `body`。

```css
body { counter-reset: section; }
h2 { font-size: 17px; color: #111827; margin-top: 2em; margin-bottom: 0.8em; counter-increment: section; }
h2::before { content: counter(section) ". "; color: #D97706; font-weight: 700; }
```

### H3 inline 斜体带句号【来自：paper】
学术论文风：H3 不独占一行，inline 跟正文流，斜体衬线，后接句号。

```css
h3 {
  font-family: Georgia, "Times New Roman", serif;
  font-size: 10px; font-weight: 700; font-style: italic; color: #000;
  display: inline; margin-top: 1em; margin-bottom: 0.4em;
}
h3::after { content: ". "; }
```

**组合建议**：H1/H2 风格可以跨模板混用——比如双栏 paper 版式配 lite 的 H2 蓝色左边框（给学术稿加一点色彩焦点）。但 H3 的 inline 斜体是 paper 专属语义，配单栏流式文档会显得"句子断不开"，单栏报告里 H3 用常规独占行更稳。medium 的 counter 编号 + paper 双栏可以共存：counter 在双栏里照样计数，但 `h2::before` 的琥珀色会和 paper 的纯黑冲淡学术感——要纯学术就别混编号色。

---

## 3. 摘要区类（Abstract）

### A1 紧贴标题无框【来自：lite】
摘要就是标题下方的居中元信息 + 紧跟正文，无 callout 包裹，最简洁。

```css
.meta { text-align: center; margin-bottom: 2em; font-size: 12px; color: #64748B; line-height: 1.6; }
.meta .authors { font-weight: 600; color: #1A1A1A; font-size: 13px; margin-bottom: 4px; }
.meta .affiliations { font-style: italic; }
/* 摘要正文直接用 <p>，无额外容器 */
```

### A2 note-box 浅底框 + 左侧色条【来自：medium】
浅底框包裹摘要，左侧 4px 色条让它从正文跳出来。源模板用蓝色条（与 medium 琥珀 accent 不同色，是有意让摘要区冷调突出）；要贴 medium 暖色系可把 `#2563EB→#D97706`、`#EFF6FF→#FFFBEB`。

```css
.note-box {
  background: #EFF6FF; border-left: 4px solid #2563EB;
  padding: 12px 16px; border-radius: 0 6px 6px 0;
  margin: 1.5em 0; font-size: 12px; color: #1E40AF;
}
.note-box strong { color: #1E40AF; }
/* 若模板自带"摘要"标题，隐藏路由进来的冗余 H2：.note-box > h2 { display: none; } */
```

### A3 上下双黑线 + small-caps 标题 + 跨双栏【来自：paper】
学术论文风：摘要上下双黑线分隔，标题大写 + 字母间距，跨双栏居中。无底色，纯靠线条划分。

```css
.abstract {
  column-span: all; -webkit-column-span: all;
  margin: 16px 0; padding: 8px 0;
  border-top: 1px solid #000; border-bottom: 1px solid #000;
}
.abstract-title {
  font-size: 10px; font-weight: 700; text-align: center;
  text-transform: uppercase; letter-spacing: 1px; margin-bottom: 6px;
  font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
}
.abstract p { font-size: 9px; text-align: justify; line-height: 1.35; color: #333; }
/* 隐藏路由进来的冗余 H2：.abstract h2 { display: none; } */
```

**组合建议（双栏里用 note-box）**：在 paper 双栏版式里塞 medium 的 note-box 摘要时，必须给 `.note-box` 加 `column-span: all`，否则它会被卡进单栏宽度，色条比例失调。结构上把 note-box 放在 `.two-col` **之前**（和 `.title-block` 同级，跨栏区），不要塞进双栏流里。配色上，双栏学术稿建议用 A3 本色（纯黑线），note-box 的彩色底和 paper 纯黑美学冲突；若要 callout 感，把 note-box 底色去掉只留左条：`background:transparent; border-left:2px solid #000`。

---

## 4. 代码块类（Code）

### C1 浅色圆角【来自：lite】
浅灰底 + 细边 + 圆角，温和不抢眼。

```css
pre {
  background: #F1F5F9; border: 1px solid #E2E8F0; border-radius: 8px;
  padding: 16px 20px; overflow-x: auto; margin: 1.2em 0;
}
pre code { font-family: Consolas, Monaco, "Courier New", monospace; font-size: 13px; line-height: 1.6; background: transparent; }
code { font-family: Consolas, Monaco, "Courier New", monospace; font-size: 0.9em; background: #F1F5F9; padding: 2px 6px; border-radius: 4px; }
```

### C2 深色带文件名标签【来自：medium】
深色底 + 右上角绝对定位文件名标签，工程报告范。`padding-top:36px` 给标签留位。

```css
.code-block { position: relative; margin: 1.2em 0; }
.code-label {
  position: absolute; top: 0; right: 0;
  background: #374151; color: #fff; font-size: 11px;
  padding: 2px 10px; border-radius: 0 8px 0 6px; z-index: 2;
  font-family: system-ui, sans-serif;
}
.code-block pre {
  background: #1E293B; color: #E2E8F0; border-radius: 8px;
  padding: 20px 20px 16px; padding-top: 36px; margin: 0; overflow-x: auto;
}
.code-block pre code { background: transparent; color: #E2E8F0; font-size: 12px; line-height: 1.7; font-family: Consolas, Monaco, monospace; }
/* inline code（medium 琥珀风） */
code { background: #FEF3C7; color: #92400E; padding: 2px 6px; border-radius: 4px; font-size: 0.9em; font-family: Consolas, Monaco, monospace; }
```

HTML 骨架：`<div class="code-block"><span class="code-label">main.py</span><pre><code>...</code></pre></div>`

### C3 浅灰极简【来自：paper】
学术稿代码：浅灰底、8px 小字、几乎无装饰，符合 data-ink 原则。

```css
pre {
  background: #F8F8F8; border: 1px solid #DDD; border-radius: 3px;
  padding: 10px 12px; font-family: Consolas, Monaco, "Courier New", monospace;
  font-size: 8px; line-height: 1.5; overflow-x: auto; margin: 1em 0;
}
code { font-family: Consolas, Monaco, monospace; font-size: 9px; padding: 1px 3px; background: #F0F0F0; border-radius: 2px; }
```

**inline code 三种风格**：lite（`#F1F5F9` 浅蓝灰底）/ medium（`#FEF3C7` 琥珀底 + `#92400E` 字色）/ paper（`#F0F0F0` 纯灰底）。

**组合建议**：双栏里放代码块必须 `break-inside: avoid`，否则会从中间被劈成两栏。深色代码块（C2）配 paper 双栏时字号要压到 8px（paper 默认就是 8px），否则深色大字块在窄栏里太抢眼。C2 的文件名标签在双栏里可能被栏间距裁切，可改 `left:0` 放左上角。短代码（<40 行）一律 `break-inside: avoid`；长代码用 C3 的 `white-space: pre-wrap; word-wrap: break-word`（paper print 段）防溢出。

---

## 5. 表格类（Table）

### T1 全框带表头底纹【来自：lite】
表头浅蓝灰底 + 下边框，单元格细底线，工程文档标配。

```css
table { width: 100%; border-collapse: collapse; margin: 1.5em 0; }
th { background: #F1F5F9; font-weight: 600; padding: 10px 14px; border-bottom: 2px solid #CBD5E1; text-align: left; }
td { padding: 10px 14px; border-bottom: 1px solid #E2E8F0; }
```

### T2 全框 + 阴影 + highlight-row 高亮行【来自：medium】
表头蓝底大写、圆角阴影容器、斑马纹、`.highlight-row` 琥珀底强调关键行。

```css
table {
  width: 100%; border-collapse: collapse; margin: 1.5em 0;
  border-radius: 8px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.08);
}
th { background: #EFF6FF; color: #1E40AF; font-weight: 600; font-size: 11px; text-transform: uppercase; letter-spacing: 0.5px; padding: 12px 14px; text-align: left; }
td { padding: 10px 14px; border-bottom: 1px solid #F3F4F6; font-size: 12px; color: #374151; }
tr:nth-child(even) td { background: #FAFAFA; }
tr:last-child td { border-bottom: none; }
.highlight-row td { background: #FEF3C7 !important; font-weight: 600; }   /* 琥珀高亮行 */
```

HTML：`<tr class="highlight-row"><td>...</td></tr>`

### T3 booktabs 三线表【来自：paper】
学术标准：仅顶底 2px 粗黑线 + 表头下 2px 线，**无竖线无横线**（Tufte data-ink）。最后一行 td 底线加粗成底线。

```css
table { width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 9px; }
th { font-weight: 700; padding: 6px 8px; text-align: center; border-top: 2px solid #000; border-bottom: 2px solid #000; }
td { padding: 5px 8px; text-align: center; border-bottom: 1px solid #CCC; }
tr:last-child td { border-bottom: 2px solid #000; }
tr td:first-child, tr th:first-child { text-align: left; }   /* 首列左对齐 */
```

**组合建议（booktabs + highlight-row）**：paper 三线表 + medium 高亮行可以共存——但三线表的精神是"墨水只载数据"，加底色高亮会破坏纯黑美学。若必须强调某行，学术稿更推荐用**粗体字**而非底色：`tr.highlight-row td { font-weight: 700; }`，去掉 `background`。长表跨页时加 `thead { display: table-header-group }` 让每页重复表头。双栏里放表只能用 T3（窄栏容不下 T2 的阴影圆角 + 多列），T1/T2 适合单栏。

---

## 6. callout/引用类（Blockquote）

### Q1 蓝色左边框【来自：lite】
纯左条 + 灰字斜体，轻量。

```css
blockquote { border-left: 4px solid #2563EB; padding-left: 16px; color: #555; font-style: italic; margin: 1.5em 0; }
```

### Q2 琥珀色左条 + 浅黄底 + 圆角【来自：medium】
左条 + 浅黄底 + 圆角，暖色 callout，最醒目。

```css
blockquote {
  background: #FFFBEB; border-left: 3px solid #D97706;
  padding: 12px 16px 12px 20px; border-radius: 0 6px 6px 0;
  margin: 1.5em 0; color: #92400E; font-style: italic;
}
```

### Q3 黑色左条【来自：paper】
2px 黑左条 + 小字斜体，学术克制。

```css
blockquote { border-left: 2px solid #000; padding-left: 12px; margin: 1em 0; font-style: italic; font-size: 9px; color: #333; }
```

**组合建议**：callout 颜色要和整体 accent 统一——lite 蓝系用 Q1，medium 琥珀系用 Q2，paper 纯黑用 Q3。跨模板混色（如 paper 双栏配 Q2 琥珀）只在"想给学术稿加一个暖色重点框"时用，且全文只能出现 1-2 次，否则破坏纯黑基调。Q2 的圆角配 paper 直角三线表会风格打架，混用时把 Q2 的 `border-radius` 去掉。

---

## 7. 页眉页脚类（Page Header/Footer）

### F1 无页眉页脚【来自：lite】
仅 `@page` margin，无 margin box。最干净，靠大边距本身留白。

```css
@page { size: A4; margin: 40mm 30mm; }
/* 无 @top-* / @bottom-* 规则 */
```

### F2 页眉文档标题 + 页脚页码 + 页脚日期【来自：medium】
`@top-center` 文档标题、`@bottom-center` 页码、`@bottom-right` 日期。日期占位 `{{DATE}}` 由脚本全模板替换。

```css
@page {
  size: A4; margin: 30mm 25mm;
  @top-center    { content: "文档标题"; font-size: 8pt; color: #9CA3AF; text-transform: uppercase; letter-spacing: 1px; }
  @bottom-center { content: counter(page); font-size: 9pt; color: #6B7280; }
  @bottom-right  { content: "{{DATE}}"; font-size: 8pt; color: #9CA3AF; }
}
/* 动态标题：h1 { string-set: doctitle content(); } 然后 @top-center { content: string(doctitle); } */
```

### F3 仅页脚页码【来自：paper】
学术稿惯例：无页眉，仅 `@bottom-center` 页码。

```css
@page { size: A4; margin: 25mm 20mm; }
@page { @bottom-center { content: counter(page); font-size: 9pt; color: #6B7280; font-family: Georgia, serif; } }
```

### 屏幕预览用的固定 .header/.footer【来自：medium/paper】
`@page` margin box 在浏览器屏幕预览不显示，所以加固定定位的 `.header/.footer` 给屏幕看，打印时隐藏。

```css
.header { position: fixed; top: 0; left: 0; right: 0; z-index: 100; text-align: center; font-size: 8pt; color: #9CA3AF; padding: 10px 25mm; background: #fff; border-bottom: 1px solid #F3F4F6; }
.footer { position: fixed; bottom: 0; left: 0; right: 0; z-index: 100; display: flex; justify-content: space-between; padding: 10px 25mm; font-size: 9pt; color: #6B7280; background: #fff; border-top: 1px solid #F3F4F6; }
@media print { .header, .footer { display: none; } }
```

**组合建议**：`@page` 的 `@top-center`/`@bottom-center` 是 PDF 打印才生效的，屏幕预览看不到——所以做屏幕预览必须额外加 `.header/.footer`（打印隐藏），两套并存。`{{DATE}}` 占位在 `@page` 规则里时，脚本必须在**全模板范围**（含 `<style>`）替换，不能只替换 body。要"每章 H1 进页眉"用 `string-set` + `string()`，单个 `@top-center` 会随 H1 切换自动变。

---

## 8. 数学/公式块（Math）

### ⚠️ LaTeX → HTML 实体转换策略（关键）

MD 里的 `$...$`（行内公式）/ `$$...$$`（块公式）LaTeX **不会自动渲染**，必须手工转 HTML 实体 + `<sub>`/`<sup>` + `<span class="math-inline">`/`<div class="math-block">`。参考 `showcase/paper/sample.html` 的公式写法。

**常用 LaTeX → HTML 实体映射表**：

| LaTeX | HTML 实体 | LaTeX | HTML 实体 |
|---|---|---|---|
| `\lambda` `\Lambda` | `&lambda;` `&Lambda;` | `\alpha \beta \gamma \delta` | `&alpha; &beta; &gamma; &delta;` |
| `\theta \sigma \omega \mu \nu` | `&theta; &sigma; &omega; &mu; &nu;` | `\phi \psi \pi \rho \tau` | `&phi; &psi; &pi; &rho; &tau;` |
| `\sum` `\prod` `\int` | `&Sigma;` `&Pi;` `&int;` | `\infty` `\partial` `\nabla` | `&infin;` `&part;` `&nabla;` |
| `\times` `\cdot` `\pm` | `&times;` `&middot;` `&plusmn;` | `\leq` `\geq` `\neq` | `&le;` `&ge;` `&ne;` |
| `\approx` `\equiv` `\propto` | `&asymp;` `&equiv;` `&prop;` | `\forall` `\exists` `\in` | `&forall;` `&exist;` `&isin;` |
| `\cap` `\cup` `\subset` `\supset` | `&cap;` `&cup;` `&sub;` `&sup;` | `\to` `\rightarrow` `\Rightarrow` | `&rarr;` `&rarr;` `&rArr;` |
| `\sqrt{x}` | `&radic;x` 或 `√x` | `\Vert a \Vert` | `&Vert;a&Vert;` |
| `\hat{x}` | `x&#770;` | `\bar{x}` | `x&#772;` | `x&#776;` |
| `\dot{x}` | `x&#775;` | `\vec{x}` | `x&#8407;` |

**上下标**：`x_i` → `x<sub>i</sub>`；`x^2` → `x<sup>2</sup>`；`x_i^2` → `x<sub>i</sub><sup>2</sup>`

**分数 `\frac{a}{b}`**：简单分数用斜杠 `a/b`；严格分数用 inline-block：
```html
<span class="frac"><span class="num">a</span><span class="den">b</span></span>
```
```css
.frac { display: inline-block; vertical-align: middle; text-align: center; margin: 0 2px; }
.frac .num { display: block; border-bottom: 1px solid currentColor; padding: 0 4px; line-height: 1.2; }
.frac .den { display: block; padding: 0 4px; line-height: 1.2; }
```

**转换示例**：

LaTeX: `$$L_{depth} = \frac{1}{N} \sum_{i} \Vert d_i - \hat{d}_i \Vert_2$$`

HTML:
```html
<div class="math-block">
  <span class="math-inline">L</span><sub>depth</sub> = <span class="frac"><span class="num">1</span><span class="den"><span class="math-inline">N</span></span></span> &Sigma;<sub><span class="math-inline">i</span></sub> &Vert;<span class="math-inline">d</span><sub><span class="math-inline">i</span></sub> &minus; <span class="math-inline">d</span>&#770;<sub><span class="math-inline">i</span></sub>&Vert;<sub>2</sub>
  <span class="math-number">(1)</span>
</div>
```

LaTeX 行内: `损失 $L = \lambda_d L_{depth} + \lambda_t L_{track}$`

HTML:
```html
<p>损失 <span class="math-inline">L = &lambda;<sub>d</sub>L<sub>depth</sub> + &lambda;<sub>t</sub>L<sub>track</sub></span>。</p>
```

> **复杂公式兜底**：矩阵用 HTML `<table>` 拼；多重积分用 `&int;&int;` 叠加；实在排不了的退化为 `<pre>` 放 LaTeX 原文 + 注释说明。

### M1 居中浅底圆角【来自：lite】
浅底圆角，Times 衬线，12pt。

```css
.math-block { text-align: center; padding: 1em; background: #FAFBFC; border-radius: 6px; margin: 1.2em 0; font-family: "Times New Roman", Times, serif; font-size: 12pt; break-inside: avoid; }
.math-inline { font-family: "Times New Roman", Times, serif; }
```

### M2 居中 + 左琥珀条【来自：medium】
浅灰底 + 左琥珀条 + 圆角，Georgia 衬线。

```css
.math-block { text-align: center; padding: 1.2em; background: #FAFAFA; border-left: 3px solid #D97706; margin: 1.5em 0; border-radius: 0 6px 6px 0; font-family: Georgia, serif; font-size: 14px; color: #1F2937; break-inside: avoid; }
.math-inline { font-family: Georgia, serif; font-style: italic; }
```

### M3 居中斜体 + 公式编号右浮动【来自：paper】
无底色，斜体衬线，`.math-number` 右浮动放公式编号 (1)(2)。学术论文标配。

```css
.math-block { text-align: center; padding: 8px 0; margin: 1em 0; font-family: Georgia, "Times New Roman", serif; font-style: italic; font-size: 11px; break-inside: avoid; }
.math-inline { font-family: Georgia, "Times New Roman", serif; font-style: italic; }
.math-number { float: right; font-size: 9px; font-style: normal; }
```

HTML：`<div class="math-block">E = mc<sup>2</sup> <span class="math-number">(1)</span></div>`

**组合建议**：双栏文档用 M3（无底色 + 右浮动编号，学术风），单栏文档可选 M1/M2（有底色框更醒目）。**双栏里公式块必须 `break-inside: avoid`**，否则公式会被劈成两栏。`.math-number` 右浮动在双栏窄栏里可能溢出，可改 `position:absolute; right:0`。要保留学术编号风格就别给公式加底色（M1/M2 的底色框会包住编号）。

---

## 9. 图占位/图片类（Figure）

### ⚠️ 图片尺寸约束策略（关键：防过大撑爆版面）

**问题**：img 只有 `max-width:100%` 在双栏里会撑满一栏（约 75mm），图片过大、不美观。

**规则**：所有图片必须包在 `<figure>` 里控尺寸。img 加 `max-height` 约束防过高。

| 场景 | figure 宽度 | img max-height | 说明 |
|---|---|---|---|
| 双栏文档单栏图 | `width: 90%` | `220px` | 默认，图在单栏内居中 |
| 双栏文档跨栏大图 | `width: 75%; column-span:all` | `280px` | 仅流程图/宽表图用 |
| 单栏文档图 | `width: 70%` | `300px` | 单栏文档默认 |
| 单栏文档大图 | `width: 90%` | `400px` | 重要大图才用 |

通用 CSS（防过大）：
```css
figure { margin: 1em 0; text-align: center; break-inside: avoid; }
figure img {
  max-width: 100%;
  max-height: 220px;   /* 关键:约束最大高度 */
  height: auto;
  display: block;
  margin: 0 auto;
  border-radius: 4px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.08);
}
figcaption { font-size: 9px; color: #555; margin-top: 6px; text-align: center; }
```

HTML 结构（所有图必须这么包）：
```html
<figure class="single-column">
  <img src="file:///D:/path/to/img.png" alt="描述">
  <figcaption>图 1:图片说明</figcaption>
</figure>
```

### P1 圆角 + 阴影【来自：lite】
图本身圆角 + 阴影，图注灰字居中。**已加 max-height 约束**。

```css
figure { margin: 1.5em 0; text-align: center; break-inside: avoid; width: 70%; margin: 1.5em auto; }
figure img { max-width: 100%; max-height: 300px; height: auto; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.08); display: block; margin: 0 auto; }
figcaption { font-size: 13px; color: #64748B; margin-top: 8px; }
```

### P2 圆角 + 阴影 + figcaption【来自：medium】
同 P1 思路，图注斜体小字。**已加 max-height 约束**。

```css
figure { margin: 1.5em auto; text-align: center; break-inside: avoid; width: 70%; }
figure img { max-width: 100%; max-height: 300px; height: auto; border-radius: 6px; box-shadow: 0 2px 12px rgba(0,0,0,0.1); display: block; margin: 0 auto; }
figcaption { font-size: 11px; color: #6B7280; margin-top: 10px; font-style: italic; }
```

### P3 双栏内单栏图 / 跨双栏图【来自：paper】
默认图在单栏内（`.single-column`）；大图跨双栏（`.full-width` + `column-span:all`）。图注 9px 居中。**已加 max-height 约束**。

```css
figure { break-inside: avoid; }
figure.full-width { column-span: all; -webkit-column-span: all; width: 75%; margin: 1.2em auto; }
figure.single-column { width: 90%; margin: 1em auto; }
figure img { max-width: 100%; max-height: 220px; height: auto; display: block; margin: 0 auto; border-radius: 4px; box-shadow: 0 1px 6px rgba(0,0,0,0.08); }
figcaption { font-size: 9px; text-align: center; margin-top: 6px; color: #555; }
```

### .figure-placeholder 占位框【来自：medium/paper】
无图时的灰底占位，flex 居中放说明文字。

```css
/* medium 版：固定尺寸 + 阴影 */
.figure-placeholder { width: 100%; max-width: 400px; height: 200px; background: #E5E7EB; border-radius: 6px; display: flex; align-items: center; justify-content: center; color: #6B7280; font-size: 12px; margin: 0 auto; box-shadow: 0 2px 12px rgba(0,0,0,0.1); }
/* paper 版：自适应 + 细边 */
.figure-placeholder { width: 100%; min-height: 150px; max-height: 200px; background: #F0F0F0; border: 1px solid #DDD; display: flex; align-items: center; justify-content: center; color: #999; font-size: 11px; }
```

**组合建议**：双栏里图默认走 `.single-column` + `max-height: 220px`，只有真正的大图（流程图/宽表图）才 `column-span: all` + `max-height: 280px`——滥用跨栏图会打断双栏阅读节奏。**图必须包 figure + max-height + break-inside:avoid**，否则会溢出栏宽或被劈开或过大撑爆版面。原则：图宽不超过版心 70%（单栏）/ 90%（双栏单栏图），图高不超过 220px（双栏）/ 300px（单栏）。

---

## 10. 参考文献类（References）

### R1 悬挂缩进 + 自动编号 [N]【来自：lite】
counter 自动生成 `[1] [2]`，悬挂缩进，灰字。

```css
.references { padding-left: 2em; text-indent: -2em; font-size: 13px; line-height: 1.6; color: #374151; list-style-type: none; counter-reset: ref-counter; }
.references li { margin-bottom: 0.6em; counter-increment: ref-counter; }
.references li::before { content: "[" counter(ref-counter) "] "; font-weight: 600; color: #1A1A1A; }
```

### R2 APA 悬挂缩进无编号【来自：medium】
悬挂缩进（`text-indent:-2em`），无编号，小字。`.cite` 内文引用蓝色。

```css
.references { padding-left: 2em; text-indent: -2em; font-size: 11px; line-height: 1.7; color: #4B5563; }
.references ol { list-style: none; padding-left: 0; }
.references li { margin-bottom: 0.5em; }
.references li::before { content: none; }
.cite { color: #1E40AF; font-size: inherit; }
```

### R3 跨双栏 + 悬挂缩进 + 小字【来自：paper】
`column-span: all` 跨双栏，8px 小字，悬挂缩进。

```css
h2#references { column-span: all; -webkit-column-span: all; }
.references { column-span: all; -webkit-column-span: all; font-size: 8px; line-height: 1.4; list-style: none; padding-left: 0; }
.references li { margin-bottom: 0.3em; padding-left: 2em; text-indent: -2em; }
.cite { /* paper 内文引用无特殊样式，纯文本 */ }
```

**组合建议**：双栏稿参考文献必须 `column-span: all`（R3），否则条目会被劈进两栏没法读。编号风格选一种：学术用 R3 无编号 APA，工程报告用 R1 `[N]` 编号 + 内文 `[1]` 引用。`.cite` 在 paper 里是纯文本（学术用 `[Smith 2020]` 文本式引用），在 medium 里是蓝色（点击感），别混。

---

## 11. 列表类（Lists）

三套的 marker 颜色差异是 accent 系统的延伸：

```css
/* 【lite】蓝色圆点 */
ul, ol { padding-left: 2em; margin-bottom: 1.2em; }
ul li::marker { color: #2563EB; }

/* 【medium】琥珀三角符（自定义 ::before，非默认 marker） */
ul { list-style: none; }
ul li::before { content: "\25B8"; color: #D97706; margin-right: 6px; display: inline-block; }
ol li { list-style: decimal; }

/* 【paper】默认黑色 disc，最克制 */
ul li { list-style: disc; }
ol li { list-style: decimal; }
```

**组合建议**：列表 marker 颜色跟着整体 accent 走。medium 的自定义三角符 `::before` 会和 `list-style:none` 配套，单拎出来用时记得把 `ul { list-style:none }` 一起带上，否则会出现默认圆点 + 三角符双重叠。

---

## 组装示例（跨模板组合）

### 示例 1：paper 双栏 + medium 琥珀 callout
**场景**：双栏学术论文版式，但摘要/重点提示想用 medium 的暖色 callout 突出（而非 paper 的纯黑线）。

```css
@page { size: A4; margin: 25mm 20mm; @bottom-center { content: counter(page); font-size: 9pt; color: #6B7280; } }
.two-col { column-count: 2; column-gap: 24px; -webkit-column-count: 2; }
.title-block { text-align: center; column-span: all; -webkit-column-span: all; margin-bottom: 12px; }
.title-block h1 { font-family: system-ui, sans-serif; font-size: 20px; color: #000; }
/* 摘要用 medium note-box，但跨栏 + 去圆角适配学术直角 */
.abstract-note {
  column-span: all; -webkit-column-span: all;
  background: #FFFBEB; border-left: 3px solid #D97706;
  padding: 12px 16px; margin: 1em 0 16px; color: #92400E; font-size: 9px;
}
/* 正文双栏，纯黑 */
h2 { font-family: system-ui, sans-serif; font-size: 12px; color: #000; break-after: avoid; }
p { font-family: Georgia, serif; font-size: 10px; text-align: justify; }
/* 引用回 paper 黑条 */
blockquote { border-left: 2px solid #000; padding-left: 12px; font-size: 9px; color: #333; break-inside: avoid; }
```

```html
<div class="title-block"><h1>论文标题</h1><div class="authors">作者 · 单位</div></div>
<div class="abstract-note"><strong>摘要</strong>　本文提出……</div>
<div class="two-col">
  <h2>引言</h2><p>正文……</p>
  <blockquote>重点引用</blockquote>
  <h2>方法</h2><p>……</p>
</div>
```
要点：note-box 必须 `column-span: all` 放在 `.two-col` **之前**；全文 callout 只用 1-2 次保持学术克制；正文 blockquote 回用 paper 黑条统一基调。

### 示例 2：lite 大边距 + medium 深色代码块
**场景**：轻量稀疏留白的阅读笔记，但代码示例用 medium 的深色带文件名标签，对比强、工程感足。

```css
@page { size: A4; margin: 40mm 30mm; }
body { font-family: system-ui, sans-serif; max-width: 680px; margin: 0 auto; padding: 60px 40px; font-size: 10.5pt; line-height: 1.8; color: #1A1A1A; }
h1 { font-size: 28px; text-align: center; border-bottom: 2px solid #2563EB; padding-bottom: 0.6em; margin-bottom: 1.5em; }
h2 { font-size: 20px; border-left: 4px solid #2563EB; padding-left: 12px; margin-top: 2em; }
/* 代码块换 medium 深色带标签 */
.code-block { position: relative; margin: 1.2em 0; break-inside: avoid; }
.code-label { position: absolute; top: 0; right: 0; background: #374151; color: #fff; font-size: 11px; padding: 2px 10px; border-radius: 0 8px 0 6px; z-index: 2; }
.code-block pre { background: #1E293B; color: #E2E8F0; border-radius: 8px; padding: 20px 20px 16px; padding-top: 36px; margin: 0; overflow-x: auto; }
.code-block pre code { background: transparent; color: #E2E8F0; font-size: 13px; line-height: 1.7; font-family: Consolas, monospace; }
/* inline code 也跟 medium 琥珀，和深色块呼应 */
code { background: #FEF3C7; color: #92400E; padding: 2px 6px; border-radius: 4px; font-family: Consolas, monospace; }
```

```html
<h1>React Hooks 笔记</h1>
<h2>useEffect 清理函数</h2>
<div class="code-block"><span class="code-label">useEffect.tsx</span><pre><code>useEffect(() => {
  const id = setInterval(tick, 1000);
  return () => clearInterval(id);
}, []);</code></pre></div>
```
要点：lite 的蓝 `#2563EB`（H1/H2）和 medium 的琥珀 `#92400E`（inline code）同框会有冷暖冲撞——若要纯净就把 inline code 也改回 lite 的 `#F1F5F9` 底，只让深色代码块作为唯一暖色焦点。

### 示例 3：medium 单栏 + paper booktabs 三线表
**场景**：正式技术报告版式（衬线 + 章节编号 + 页眉页脚），但表格用学术三线表，比 medium 默认的阴影圆角表更克制专业。

```css
@page {
  size: A4; margin: 30mm 25mm;
  @top-center { content: string(doctitle); font-size: 8pt; color: #9CA3AF; text-transform: uppercase; letter-spacing: 1px; }
  @bottom-center { content: counter(page); font-size: 9pt; color: #6B7280; }
  @bottom-right { content: "{{DATE}}"; font-size: 8pt; color: #9CA3AF; }
}
h1 { string-set: doctitle content(); font-size: 24px; text-align: center; color: #111827; }
body { counter-reset: section; font-family: Georgia, serif; font-size: 12px; line-height: 1.6; color: #333; }
main { max-width: 720px; margin: 0 auto; }
h2 { font-size: 17px; color: #111827; margin-top: 2em; counter-increment: section; }
h2::before { content: counter(section) ". "; color: #D97706; font-weight: 700; }
/* 表格换 paper booktabs 三线表 */
table { width: 100%; border-collapse: collapse; margin: 1.5em 0; font-size: 11px; }
th { font-weight: 700; padding: 8px 10px; text-align: left; border-top: 2px solid #000; border-bottom: 2px solid #000; color: #111827; }
td { padding: 6px 10px; border-bottom: 1px solid #CCC; color: #374151; }
tr:last-child td { border-bottom: 2px solid #000; }
/* 强调行用粗体而非底色，保 booktabs 纯净 */
.highlight-row td { font-weight: 700; }
thead { display: table-header-group; }   /* 长表跨页重复表头 */
```

```html
<h1>季度技术评审报告</h1>
<main>
  <h2>指标对比</h2>
  <table>
    <thead><tr><th>指标</th><th>Q1</th><th>Q2</th></tr></thead>
    <tbody>
      <tr><td>延迟</td><td>120ms</td><td>85ms</td></tr>
      <tr class="highlight-row"><td>吞吐</td><td>1.2k</td><td>2.4k</td></tr>
    </tbody>
  </table>
</main>
```
要点：booktabs 进 medium 单栏要把字号从 paper 的 9px 提到 11px（适配 medium 12px 正文）；高亮行用粗体不用底色，保三线表纯净；`thead { display: table-header-group }` 让长表跨页重复表头。

---

## 结尾提醒（拼装自检清单）

- **颜色硬编码**：所有 hex 直接写（如 `#2563EB`），**不用 `var(--color-*)` 外部变量**——custom.html 要自洽可预览，浏览器直接打开就能看效果。
- **@page + break 规则必须有**：`@page { size:A4; margin:... }` 是底线；标题 `break-after:avoid`、图表/代码/引用 `break-inside:avoid`、长表 `thead{display:table-header-group}`。
- **图片兜底**：`img { max-width:100%; height:auto; break-inside:avoid }`，防溢出防跨页劈裂。
- **兜底区域**：必须有 `{{EXTRA}}` 或 `{{BODY}}` 类的容器接收未匹配内容，别让漏掉的章节丢失。
- **首页 H1**：用 `break-before:avoid` 覆盖默认强制分页，否则首页空白。
- **屏幕预览**：`@page` margin box 屏幕不显示，加固定 `.header/.footer`（`@media print{display:none}`）给浏览器看。
- **看完整效果**：拼装前先翻 `references/showcase/{lite,medium,paper}/sample.html`，那里有填好假数据的完整渲染样例，比单看 CSS 片段更直观。
