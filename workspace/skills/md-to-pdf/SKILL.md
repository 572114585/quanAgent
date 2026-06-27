---
name: md-to-pdf
description: "把 Markdown(可多源)整理后渲染为带印刷级排版的 HTML 中间产物,再用 Playwright 转为 PDF。当用户要把 Markdown 或 Markdown 集合做成排版精良的 PDF 文档时调用。不用于纯文本提取、PPT、网页交互原型。"
allowed-tools: execute read_file write_file edit_file
---

# MD to PDF

本 skill 把 Markdown(单个或多个)做成排版精良的 PDF。**LLM 参考 showcase 真实渲染示例 + 零件目录,自行设计 HTML 再转 PDF**——既有模板范式参考,又能自由发挥设计。

```
MD(多源) ─[merge: 默认保图]─► 合并MD ─[plan: 参考showcase+零件目录]─► LLM write_file custom.html ─[render_pdf.py: Playwright]─► PDF
```

**核心定位:印刷级排版**,不是"能看就行"。强制产出 HTML 中间产物 + Checkpoint 预览。

### 工作流概览
1. 翻 `references/showcase/{lite,medium,paper}/sample.html` 选整体范式(真实渲染示例,浏览器直接打开看效果)
2. 从 `references/component-catalog.md` 挑零件组装(布局/标题/摘要/代码/表格/callout/页眉页脚/数学/图/参考文献 11 类,每类多变体 + 跨模板组合示例)
3. `write_file output/custom.html`(内嵌完整 CSS,自包含,公式用 HTML 实体手工排版,图片包 figure 控尺寸)
4. `render_pdf.py --html output/custom.html --out output/custom.pdf`

> 历史背景:早期版本用"套死模板"模式(4 个自包含模板 + md_to_html.py 脚本路由 slot),LLM 选模板时看不到渲染效果、无法跨模板借鉴组件,导致"模板没参考价值"。现重构为单一自由设计模式,删掉模板和路由脚本,只保留 showcase 真实示例 + 零件目录作为参考素材。

---

## 范围

✅ **适用**:Markdown → 排版 PDF(日报 / 技术报告 / 学术论文 / 白皮书 / 电子书 / 产品手册)
✅ **适用**:多个 MD 合并为单一 PDF(顺序拼接 / 主题重组 / 独立章节)
❌ **不适用**:PPT / 幻灯片(用 `web-design-engineer` 的 slide deck)
❌ **不适用**:交互式网页原型(无打印语义)
❌ **不适用**:从 PDF/Word/Excel 抽取 MD(用 `mineru` skill,把抽取结果再喂给本 skill)

---

## 流水线架构

| 阶段 | 脚本/动作 | 说明 |
|---|---|---|
| **1. 合并** | `scripts/merge_sources.py` | 多源 MD → 单 MD(默认保图)。单一 MD 跳过 |
| **2. 规划** | LLM 决策(无脚本) | 参考 showcase + 零件目录,设计 HTML 骨架 + 组件选型 + 配色 |
| **3. 渲染 HTML** | LLM `write_file output/custom.html` | 内嵌完整 CSS,自包含。公式用 HTML 实体,图片包 figure |
| **4. 渲染 PDF** | `scripts/render_pdf.py` | Playwright async,HTML → PDF |

> **HTML 是必经中间产物,不是副作用**。它让用户在烧成 PDF 前可以预览、改 CSS、改内容。永远要产出 HTML 中间产物(Checkpoint 2 预览强制),不要跳过 HTML 直接 MD→PDF。

---

## ⚠️ 图片硬规则(违反必返工)

**默认保留所有图片**。源 MD 里的 `![](...)` 在内容整合、合并、规划、渲染各阶段都不允许丢失,除非用户**显式**要求去掉。

0. **LLM 内容整合阶段(最易丢图,必读)**:当输入是多源 MD 需要整合成一篇汇报/综述/报告(而非简单拼接)时,整合由 LLM 用语义重写完成。**LLM 在重写时默认会把图片引用当成源文档附属物丢掉**——这是丢图的最常见根因,与 `merge_sources.py` 无关。
   - 整合时必须**显式指令 LLM 保留所有源 MD 的 `![](...)` 图片引用**,并就近嵌入到整合后对应章节
   - 整合后的 MD 图片总数 **必须 ≥ 源 MD 图片总数之和**
   - 整合完立即自检:数一下整合 MD 的 `![](` 出现次数,与源对比。少一张都要回 LLM 补
   - **整合指令模板**(用户让 LLM 整合多源 MD 时直接套用):

     ```
     请把以下多份 Markdown 整合成一篇连贯的汇报文档。硬规则:
     1. 保留源文档中所有图片引用 ![](...),一张不许丢。整合后图片数不得少于源图片总数。
     2. 图片就近嵌入到整合后语义最相关的章节(如论文的方法图放在"方法"节、结果图放在"结果"节)。
     3. 不要用"如图所示"代替图片——图本身必须保留。
     4. 若某张图在整合后的章节里无处安放,放到"附录:原始素材图"节,不许删除。
     5. 图片的 alt 文本与路径原样保留,不要改写路径。
     输出整合后的完整 Markdown。
     ```

1. **合并阶段**:`merge_sources.py` 默认重写相对图片路径为 `file://` 绝对路径(按源文件目录解析),避免合并后路径失效。仅当传 `--strip-images` 才移除图片。
2. **合并后必须核对图片计数**:脚本输出"源共 N 张,合并后 M 张"。若 M < N 且未传 `--strip-images`,会打印 `[WARN]`,此时必须排查 thematic 策略的 H2 切块是否丢了图。
3. **规划阶段**:路由 H2 到 slot 时,图片随其所属 H2 块走,不单独剥离。详细工作/结果章节的图是内容的一部分。
4. **渲染阶段**:`md_to_html.py` 不修改图片引用,但会在渲染前统计输入 MD 图片数并打印 `[INFO] 输入 MD 含 N 张图片`。若 N=0 会打印 `[WARN]`,提示上游 LLM 内容整合可能丢图。模板的布局 CSS 只约束图片尺寸/边距,不删除图片。
5. **占位符 ≠ 丢图**:只有当源 MD 本身缺图时才用 `[image: 说明]` 占位符。源 MD 有图却丢图,是 bug。

> 用户说"去掉图片"才用 `--strip-images`;说"精简"不等于去图;说"排版"不等于去图;说"整合/汇报/综述"更不等于去图——整合时要带图走。

### 丢根因速查表

| 症状 | 根因 | 排查 |
|---|---|---|
| 整合 MD 一张图都没有 | LLM 内容整合语义重写时丢图(最常见) | 数整合 MD 的 `![](` 次数,与源对比;用上面整合指令模板重跑 |
| 合并后图变少 | `merge_sources.py` thematic 切块丢图 | 看 merge 输出的"源共 N 张,合并后 M 张"行 |
| HTML 里图路径错 | 相对路径未重写 | 确认 merge 未加 `--no-rewrite-paths` |
| PDF 里图空白 | 路径对但文件不存在/网络超时 | 看 render_pdf 的"加载失败"列表 |

---

## ⚠️ 命令格式硬规则(违反会被 runtime 拦截)

1. **命令必须单行**:`execute(command=...)` 的 command 是单行字符串,禁止反斜杠续行或裸换行。
2. **中文/JSON 用双引号包裹,内部双引号用 `\"` 转义**。
3. **只调用本 skill 自带脚本**(`merge_sources.py` / `render_pdf.py`)。禁止 `write_file` 自写 `.py` 脚本再 `execute`——runtime 白名单会拦截。**允许 `write_file` 直接写 `.html`**(LLM 设计 HTML → `write_file output/custom.html` → `render_pdf.py --html`)。
4. **输出只写 `output/`**:`write_file`/`edit_file` 受限,`skills/` 目录只读。`custom.html` 也放 `output/`。

脚本路径(workspace 根目录为工作目录):

```
skills/md-to-pdf/scripts/merge_sources.py
skills/md-to-pdf/scripts/render_pdf.py
```

先 `python <script> --help` 查看完整参数。输出文件放 `output/`,如 `output/custom.html`、`output/custom.pdf`。

---

## 工作流程

### Step 0:确认输入与目标(决定是否问)

| 场景 | 问吗 |
|---|---|
| "把这两个 MD 合成一个 PDF" | ⚠️ 只问合并策略(sequential/thematic/standalone) |
| "把这份 MD 做成排版好看的 PDF" | ✅ 问:文档类型、读者、纸张、视觉倾向 |
| "用学术论文格式把这份 MD 转 PDF" | ❌ 够了,参考 showcase/paper/sample.html 双栏范式 |
| "做个 PDF,不知道什么风格" | ⚡ 翻 showcase 三套示例给建议 |
| "想要双栏论文但摘要用琥珀 callout" | ❌ 够了,跨模板组合直接做 |

关键探查项(按需挑):
- **文档类型 + 视觉倾向**(决定参考哪套 showcase 范式):
  - 轻量技术笔记 / 稀疏留白 → 参考 `showcase/lite`(蓝 accent、无衬线、大边距、单栏)
  - 正式技术评审 / 月度总结 / 跨团队提案 → 参考 `showcase/medium`(琥珀、Georgia 衬线、章节自动编号、note-box 摘要)
  - 学术论文 / 双栏 / 图表密集 → 参考 `showcase/paper`(双栏、booktabs 三线表、纯黑无彩)
  - 日报 / 周报 / 站会纪要 → 参考 `showcase/lite` 的单栏 + 自定义左1/3右2/3 网格(见零件目录 L4)
  - 跨模板组合(如"双栏论文带琥珀 callout")→ 混合参考多套
- **读者**:内部团队 / 客户 / 公开发布 / 学术评审
- **纸张**:A4 / Letter / B5;是否双面;是否需要装订边
- **多源策略**(仅多 MD 时):sequential(顺序)/ thematic(按主题重组)/ standalone(各自独立章节)
- **图片**:默认保留。仅当用户明确"去掉图片"才记 `--strip-images`
- **公式**:MD 里有 `$...$`/`$$...$$` 吗?有则按 Step 3 公式处理规则转 HTML 实体

### Step 1:合并多源(仅多 MD 时)

```bash
execute(command="python skills/md-to-pdf/scripts/merge_sources.py --help")
```

三种策略:

| 策略 | 行为 | 适用 |
|---|---|---|
| `sequential`(默认) | 按 `--inputs` 顺序拼接,每个 MD 之间插分页符 | 多份独立报告合并 |
| `thematic` | 提取所有 H1/H2,按主题重新归类成新章节 | 多源资料按主题整合 |
| `standalone` | 每个 MD 作为独立"部"(Part),带部首页 | 章节式电子书 |

```bash
execute(command="python skills/md-to-pdf/scripts/merge_sources.py --inputs '[\"output/ch1.md\",\"output/ch2.md\"]' --strategy sequential --out output/merged.md")
```

合并后**必须核对输出里的图片计数行**:`图片:源共 N 张,合并后 M 张`。若出现 `[WARN] 合并后图片数少于源总数`,说明 thematic 切块丢了图,必须排查重跑。除非用户明确要求,不要加 `--strip-images`。

> 单一 MD 输入时跳过此步,直接进 Step 2。

### Step 2:规划内容 + 设计 HTML 骨架(写代码前必须做)

本步是**规划阶段**:参考 showcase 选范式 + 从零件目录挑组件,设计 HTML 骨架,然后给用户看预览。

**2a. 参考选型**

1. 翻 `references/showcase/{lite,medium,paper}/sample.html` 选整体范式(浏览器打开看真实渲染效果,三套都是 D4RT 论文示例)
2. 从 `references/component-catalog.md` 挑零件(11 类:布局/标题/摘要/代码/表格/callout/页眉页脚/数学/图/参考文献/列表,每类多变体 + 跨模板组合示例)
3. 设计 HTML 骨架(分区 + 组件选型 + 配色/字体)

**2b. 声明并预览设计**

```markdown
Design Decisions:
- 范式参考:showcase/paper/sample.html(双栏学术论文)+ showcase/medium/sample.html(note-box callout)
- 纸张:A4
- 组件选型(从 component-catalog.md 挑):
    - 布局:L3 双栏(column-count:2,gap 24px)
    - 标题:H1 跨双栏居中(paper 风系统字体)
    - 摘要:A2 note-box 浅底框(改琥珀色 #D97706/#FFFBEB,跨双栏 column-span:all)
    - 代码:C2 深色带文件名标签(medium 风)
    - 表格:T3 booktabs 三线表(paper 风)
    - 页眉页脚:F3 仅页脚页码(paper 风)
- 配色:墨 #1D1D1F + 琥珀 accent #D97706(跨模板组合:paper 版式 + medium 配色)
- 图片:保留(默认),包 figure 控尺寸(见 Step 3 图片处理)
- 公式:MD 里的 $...$/$$...$$ 转 HTML 实体手工排版(见 Step 3 公式处理)
- 输出:output/custom.html(内嵌完整 CSS,自包含)
```

🛑 **Checkpoint 1**:声明后停下,告诉用户"我打算用这套范式 + 组件选型 + 配色,确认后我开始写 HTML"。**真的等**,别说完就开干。特别要让用户确认**组件选型 + 配色**——这是自由设计的核心决策。

### Step 3:渲染 HTML(LLM 自由设计)

LLM 直接 `write_file output/custom.html` 产出 HTML。流程:

1. **解析 MD 内容**:读取合并后的 MD,理解章节结构(H1/H2/H3)、图片位置、表格、代码块、公式等
2. **参考 showcase 选范式**:读 `references/showcase/{lite,medium,paper}/sample.html` 选整体布局风格(浏览器打开看效果)
3. **从零件目录挑组件**:读 `references/component-catalog.md`,按 11 类挑组件(布局/标题/摘要/代码/表格/callout/页眉页脚/数学/图/参考文献/列表),可跨模板组合
4. **`write_file output/custom.html`**:产出自包含 HTML(CSS 全 inline 进 `<style>`,不依赖外部文件),内容来自 MD,版式来自组件选型

产出的 HTML 必须满足:
- **自包含**:CSS 全 inline,浏览器直接打开能看完整效果
- **印刷友好**:`@page` 定义 size + margin + 页眉页脚;`break-before/after/inside` 规则完整
- **图片保留 + 控尺寸**:MD 里的 `![](...)` 全部保留,路径已是 `file://` 绝对路径(merge 阶段重写过)。**图片必须包在 `<figure>` 里控尺寸**(见下方图片处理)
- **公式正确渲染**:MD 里的 `$...$`/`$$...$$` 转 HTML 实体手工排版(见下方公式处理)
- **配色硬编码**:不用 `var()` 外部变量,颜色直接写 hex
- **无 AI 俗套**:无紫粉渐变/emoji/Inter 当正文(详见"反 AI 俗套"章节)
- **兜底**:所有 MD 内容都有去处,不丢章节

#### 图片处理(关键:控尺寸防过大)

**问题**:img 只有 `max-width:100%` 在双栏里会撑满一栏(约 75mm),图片过大、不美观。

**规则**:所有图片必须包在 `<figure>` 里,用 figure 控制宽高 + 居中 + 图注。img 加 `max-height` 约束防过高。

```html
<!-- 单栏内图(双栏文档的默认)-->
<figure class="single-column">
  <img src="file:///D:/path/to/img.png" alt="描述">
  <figcaption>图 1:图片说明</figcaption>
</figure>

<!-- 跨双栏大图(流程图/宽表图才用)-->
<figure class="full-width">
  <img src="file:///D:/path/to/overview.png" alt="概览">
  <figcaption>图 2:系统概览</figcaption>
</figure>
```

CSS(从 component-catalog.md P3 改良):
```css
figure { margin: 1em 0; text-align: center; break-inside: avoid; }
figure.full-width { column-span: all; -webkit-column-span: all; width: 75%; margin: 1.2em auto; }
figure.single-column { width: 90%; margin: 1em auto; }
figure img {
  max-width: 100%;
  max-height: 220px;   /* 关键:约束最大高度,防止图过大撑爆版面 */
  height: auto;
  display: block;
  margin: 0 auto;
  border-radius: 4px;
  box-shadow: 0 1px 6px rgba(0,0,0,0.08);
}
figcaption { font-size: 9px; color: #555; margin-top: 6px; text-align: center; }
```

> 单栏文档(非双栏)的图:`figure { width: 70%; margin: 1.2em auto; }` + `img { max-height: 300px; }`。原则:图宽不超过版心 70%,图高不超过 220px(双栏)/ 300px(单栏)。

#### 公式处理(关键:HTML 实体手工排版)

**问题**:MD 里的 `$...$`/`$$...$$` LaTeX 公式不会自动渲染,需手工转 HTML。

**规则**:把 LaTeX 转成 HTML 实体 + `<sub>`/`<sup>` + `<span class="math-inline">`/`<div class="math-block">`。参考 `showcase/paper/sample.html` 的公式写法。

**常用 LaTeX → HTML 实体映射**:

| LaTeX | HTML 实体 | 说明 |
|---|---|---|
| `\lambda` | `&lambda;` | 希腊字母小写 |
| `\Lambda` | `&Lambda;` | 希腊字母大写 |
| `\alpha \beta \gamma \delta \theta \sigma \omega` | `&alpha; &beta; &gamma; &delta; &theta; &sigma; &omega;` | 常用希腊字母 |
| `\sum` | `&Sigma;` 或 `&sum;` | 求和 |
| `\prod` | `&Pi;` 或 `&prod;` | 连乘 |
| `\int` | `&int;` | 积分 |
| `\infty` | `&infin;` | 无穷 |
| `\partial` | `&part;` | 偏导 |
| `\nabla` | `&nabla;` | 梯度 |
| `\times` | `&times;` | 叉乘 |
| `\cdot` | `&middot;` | 点乘 |
| `\pm` | `&plusmn;` | 正负 |
| `\leq \geq` | `&le; &ge;` | 不等号 |
| `\neq` | `&ne;` | 不等 |
| `\approx` | `&asymp;` | 约等 |
| `\equiv` | `&equiv;` | 同余 |
| `\forall \exists` | `&forall; &exist;` | 量词 |
| `\in` | `&isin;` | 属于 |
| `\cap \cup` | `&cap; &cup;` | 集合交并 |
| `\subset \supset` | `&sub; &sup;` | 子集超集 |
| `\to \rightarrow` | `&rarr;` | 箭头 |
| `\Rightarrow` | `&rArr;` | 双线箭头 |
| `\sqrt{x}` | `&radic;x` 或 `√x` | 根号 |
| `\Vert a \Vert` | `&Vert;a&Vert;` | 范数 |
| `\hat{x}` | `x&#770;` | 帽子(估计值) |
| `\bar{x}` | `x&#772;` | 上划线 |

**上下标**:
- `x_i` → `x<sub>i</sub>`
- `x^2` → `x<sup>2</sup>`
- `x_i^2` → `x<sub>i</sub><sup>2</sup>`

**分数 `\frac{a}{b}`**:简单分数用斜杠 `a/b`;需要严格分数用 inline-block:
```html
<span class="frac"><span class="num">a</span><span class="den">b</span></span>
```
```css
.frac { display: inline-block; vertical-align: middle; text-align: center; }
.frac .num { display: block; border-bottom: 1px solid currentColor; padding: 0 3px; }
.frac .den { display: block; padding: 0 3px; }
```

**行内公式** `$...$`:
```html
<p>损失函数 <span class="math-inline">L</span> 由三部分组成:<span class="math-inline">L = &lambda;<sub>d</sub>L<sub>depth</sub> + &lambda;<sub>t</sub>L<sub>track</sub></span>。</p>
```

**块公式** `$$...$$`(带编号):
```html
<div class="math-block">
  <span class="math-inline">L</span><sub>depth</sub> = (1/<span class="math-inline">N</span>) &Sigma;<sub><span class="math-inline">i</span></sub> &Vert;<span class="math-inline">d<sub>i</sub></span> &minus; <span class="math-inline">d&#770;<sub>i</sub></span>&Vert;<sub>2</sub>
  <span class="math-number">(1)</span>
</div>
```

**CSS**(从 component-catalog.md M3):
```css
.math-block {
  text-align: center;
  padding: 8px 0;
  margin: 1em 0;
  font-family: Georgia, "Times New Roman", serif;
  font-style: italic;
  font-size: 11px;
  break-inside: avoid;   /* 双栏里公式块不能被劈开 */
}
.math-inline {
  font-family: Georgia, "Times New Roman", serif;
  font-style: italic;
}
.math-number {
  float: right;
  font-size: 9px;
  font-style: normal;
}
```

> **复杂公式(矩阵/多重积分)处理**:HTML 实体手工排版吃力。遇到矩阵用 HTML `<table>` 拼,多重积分用 `&int;&int;` 叠加。若实在排不了,退化为代码块 `<pre>` 放 LaTeX 原文 + 注释说明。

#### HTML 骨架示例(伪代码)

```html
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<title>文档标题</title>
<style>
/* 从 component-catalog.md 挑的组件 CSS,按选型拼接 */
@page { size: A4; margin: 25mm 20mm; @bottom-center { content: counter(page); ... } }
/* L3 双栏 */ .two-col { column-count: 2; column-gap: 24px; }
/* A2 note-box */ .note-box { background: #FFFBEB; border-left: 4px solid #D97706; ... }
/* T3 booktabs */ table { border-top: 2px solid #000; ... }
/* 图片控尺寸(见上方)*/ figure { ... } figure img { max-height: 220px; ... }
/* 公式(见上方)*/ .math-block { ... } .math-inline { ... }
</style>
</head>
<body>
<!-- 标题区(跨双栏)-->
<div class="title-block"><h1>文档标题</h1><div class="authors">作者</div></div>
<!-- 摘要(note-box,跨双栏)-->
<div class="note-box">摘要内容</div>
<!-- 双栏正文 -->
<div class="two-col">
  <h2>章节</h2>
  <p>正文,含 <span class="math-inline">x<sub>i</sub></span> 行内公式。</p>
  <div class="math-block">块公式 <span class="math-number">(1)</span></div>
  <figure class="single-column"><img src="..." /><figcaption>图 1</figcaption></figure>
</div>
</body>
</html>
```

### Step 4:HTML 预览检查点(必做)

🛑 **Checkpoint 2**:**渲染 PDF 前,先让用户看 HTML**。

- 用浏览器打开 `output/custom.html`(或截图)
- 检查:排版方向对吗?字号舒适吗?配色对吗?分页逻辑对吗?**公式显示对吗?** **图片尺寸合理吗(不撑爆版面)?** 摘要/参考文献是否重复出现?
- HTML 是中间产物,改 CSS 比改 PDF 容易 100 倍——这一步省下来后面要还债

用户确认后再进 Step 5。

### Step 5:渲染 PDF(Playwright)

```bash
execute(command="python skills/md-to-pdf/scripts/render_pdf.py --help")
```

```bash
execute(command="python skills/md-to-pdf/scripts/render_pdf.py --html output/report.html --out output/report.pdf --page-size A4")
```

脚本内部使用 **async API**(与项目 FastAPI 栈兼容),关键参数(已验证):
- `wait_until='networkidle'`(等网络图片加载完)
- 加载后延时 1s(等字体/Chart.js 渲染)
- `print_background=True`(保留背景色)
- `format` / `margin` 来自 `--page-size` 与模板的 `@page` 配置

### Step 6:验证

```bash
execute(command="python skills/md-to-pdf/scripts/render_pdf.py --verify output/report.pdf")
```

检查:文件大小(0 字节=失败)、页数、首尾页截图。汇报:路径、页数、大小、使用的模板。

### Step 7:按需自检(用户要求"看看好不好"时)

跑**5 维度自检**:

| 维度 | 评估点 |
|---|---|
| **模板一致性** | 配色/字体是否忠实于所选模板的视觉签名?还是漂移成 AI 默认? |
| **视觉层级** | 眯眼测试通过?H1/正文比例 ≥ 2.5×? |
| **工艺质量** | 间距系统统一(8pt 网格)?配色 ≤ 4 种?字体 ≤ 2 族? |
| **印刷友好** | 无内容溢出?表格不跨页断裂?代码块不超页边?图片不变形? |
| **原创性** | 避免俗套?有没有"意外但正确"的决策? |

---

## 硬规则:反 AI 俗套(打印版)

| 模式 | 为什么是 slop | 何时其实可以 |
|---|---|---|
| 紫粉蓝渐变背景 | AI 训练数据收敛的"科技感"公式,打印出来更糟(费墨且廉价感) | 模板明确要求 |
| 圆角卡片 + 左侧色条 | Material/Tailwind 残留,在 PDF 里是噪音 | 模板明确要求(如 daily-report 摘要 callout 的左侧 accent 条是刻意设计) |
| Emoji 当图标 | 不专业,且部分字体渲染异常 | 永远不用 |
| Inter / Roboto / Arial 当正文 | 太常见,读起来像"AI 生成的报告" | 模板指定(report-lite 用 system-ui 是刻意工程感;report-medium/paper 用 Georgia 衬线是正式感) |
| `#0D1117` 暗色背景配霓虹色 | GitHub-dark 角色扮演,打印费墨且不专业 | 永远不用 |
| 编造数据/假引用/假图表 | 损害可信度,PDF 比 Web 更难追改 | **永远不行**——用占位符标注"此处需要真实数据" |

### Emoji 规则

**永远不用**。打印文档里 emoji 不专业,且部分字体渲染异常。

### 占位符哲学

缺图片/数据时,**占位符比假货专业**:
- 缺图 → `[image: 16:9 说明]` 文字占位框(不画 CSS 假图)
- 缺数据 → 显式标注 `[此处需要真实数据: xxx]`
- 缺引用 → `[citation needed: xxx]`

---

## 印刷 CSS 关键规则(LLM 设计 HTML 时遵循,详见 `references/print-css.md`)

```css
@page {
  size: A4;
  margin: 25mm 25mm 30mm 25mm;  /* 装订侧加宽 */
  @bottom-center { content: counter(page); }  /* 页脚页码 */
  @top-center { content: string(doc-title); }  /* 页眉标题 */
}
@page :first { margin: 0; }  /* 封面无页边距 */

h1 { break-before: page; }  /* H1 强制新页 */
h2, h3 { break-after: avoid; }  /* 标题不与下文分离 */
pre, table, figure { break-inside: avoid; }  /* 代码/表/图不分页 */
img { max-width: 100%; height: auto; }  /* 图片不溢出 */
```

> LLM 设计 HTML 时按所选范式(showcase lite/medium/paper)的 `@page` 配置参考:lite 大边距 40mm、medium 标准 25mm、paper 紧凑 25mm。双栏文档用 paper 的 25mm 20mm。

---

## 前置依赖

- **Python 3.10+**(项目已有 3.13.12 ✓)
- **Playwright + Chromium**:`pip install playwright && playwright install chromium`(项目已装 ✓)

---

## 交付前清单

完成以下全部后才算交付:

- [ ] 多源时执行了 Step 1 合并,并确认策略
- [ ] 合并后图片计数核对通过(无 `[WARN]` 或已排查)
- [ ] Step 2 声明了**范式 + 组件选型 + 配色**,用户确认后再写代码
- [ ] HTML 中间产物已生成,用户已预览(Checkpoint 2)
- [ ] HTML 自包含(CSS 全 inline,浏览器直接打开能看效果)
- [ ] 组件选型与 Step 2 声明一致,配色硬编码无 `var()` 外部变量
- [ ] **公式正确渲染**(MD 的 `$...$`/`$$...$$` 转 HTML 实体,无未转换的 LaTeX 残留)
- [ ] **图片尺寸合理**(包 figure 控尺寸,max-height 约束生效,不撑爆版面)
- [ ] PDF 渲染无报错,文件大小 > 0
- [ ] 首尾页截图正常,无空白页/无内容溢出
- [ ] 表格/代码块/图片未跨页断裂
- [ ] **图片全部保留**(除非用户明确要求去掉)
- [ ] 页眉页脚页码正确(@page 规则按设计生效)
- [ ] 配色全部来自所选组件的 CSS——无 rogue hue
- [ ] 摘要/参考文献标题未重复出现
- [ ] 无 AI 俗套(紫粉渐变/emoji/Inter 当正文)
- [ ] 无编造数据,缺失处用占位符标注
- [ ] 输出文件在 `output/` 下,路径已汇报给用户

---

## References 路由

所有 `references/...` 路径相对本 skill 目录。按任务类型按需读取,不要全量预载:

| 任务 | 读 |
|---|---|
| **看真实渲染示例选范式**(lite/medium/paper 三套 D4RT 论文示例,CSS inline,浏览器直接打开看效果) | `references/showcase/{lite,medium,paper}/sample.html` |
| **挑组件拼装自定义 HTML**(11 类零件:布局/标题/摘要/代码/表格/callout/页眉页脚/数学/图/参考文献/列表,每类多变体 + 跨模板组合示例) | `references/component-catalog.md` |
| **查组件 CSS 源**(零件目录引用的 CSS 原文) | `references/showcase/{lite,medium,paper}/components.css` |
| 排版要点(网格/层级/信息密度/图片位置,按文档类型分章) | `references/layout-principles.md` |
| 需要打印 CSS 细节(`@page`/分页/字号/字体加载) | `references/print-css.md` |

---

## 与其他 skill 的协作

| 上游 | 下游 |
|---|---|
| `mineru`(PDF/Word/Excel → MD) → 把 MD 喂给本 skill | 本 skill 输出 PDF → 可用 `pdf-generator-1.0.1/scripts/edit.py` 合并/加水印/拆分 |
| `word-docx` / `excel-xlsx`(若已有 MD 形式的内容) | |

典型链路:扫描件 PDF → `mineru` 抽 MD → 本 skill 排版 PDF。
