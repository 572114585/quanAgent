# Print CSS System — 印刷级排版参考

本文件是 `md-to-pdf` skill 的打印 CSS 技术参考。所有自包含模板(`templates/*.html`)的 `@page` 与分页配置都基于此处的规则;脚本 `md_to_html.py` 在 generic 模式下生成的 BASE_CSS 也遵循这些约定。

> 本文件只讲**打印介质**特有的规则。屏幕端 CSS 最佳实践(CSS 变量、oklch、Grid/Flex)不在此重复,见 `web-design-engineer` 的 `advanced-patterns.md`。

---

## 1. `@page` 规则

### 1.1 基本结构

```css
@page {
  size: A4;                              /* A4 | Letter | B5 | { width height } */
  margin: 25mm 25mm 30mm 30mm;           /* 上 右 下 左(装订侧左加宽) */
  @top-center { content: string(doc-title); font-size: 9pt; color: #666; }
  @bottom-center { content: counter(page); font-size: 9pt; color: #666; }
  @top-right { content: "文档标题"; }     /* 可选 */
}
```

### 1.2 命名页(封面差异化)

```css
@page :first {                          /* 第一页:封面,无页眉页脚 */
  margin: 0;
  @top-center { content: none; }
  @bottom-center { content: none; }
}

@page cover {                           /* 命名页,用 `page: cover` 应用 */
  margin: 0;
  background: #F1ECDE;
}

@page chapter {                         /* 章节首页:无页眉 */
  @top-center { content: none; }
  margin-top: 40mm;
}

.cover-page { page: cover; }
.chapter-opener { page: chapter; }
```

### 1.3 双面打印(左右页镜像)

```css
@page :left {                           /* 左页(偶数页) */
  margin-left: 30mm;                    /* 装订侧 */
  margin-right: 20mm;
  @left-top { content: "左页眉"; }
}
@page :right {                          /* 右页(奇数页) */
  margin-left: 20mm;
  margin-right: 30mm;                   /* 装订侧 */
  @right-top { content: "右页眉"; }
}
```

### 1.4 纸张尺寸速查

| 尺寸 | `size` 值 | 物理尺寸 | 常见用途 |
|---|---|---|---|
| A4 | `A4` | 210×297mm | 默认,国际通用 |
| Letter | `Letter` | 8.5×11in | 北美 |
| B5 | `B5` | 176×250mm | 书籍/手册 |
| A5 | `A5` | 148×210mm | 小册子 |
| Legal | `Legal` | 8.5×14in | 法律文件 |

---

## 2. 分页控制

### 2.1 强制分页

```css
h1 { break-before: page; }              /* H1 总是新起一页 */
.cover-page { break-after: page; }      /* 封面后必分页 */
hr.page-break { break-after: page; }    /* 手动分页符 */
```

### 2.2 避免分页(标题不与内容分离)

```css
h1, h2, h3, h4, h5, h6 {
  break-after: avoid;                   /* 标题不孤悬页底 */
  break-inside: avoid;
}
h2 + p, h3 + p { break-before: avoid; } /* 标题与首段不分页 */
```

### 2.3 块级元素不分页

```css
pre, table, figure, blockquote {
  break-inside: avoid;                  /* 代码块/表格/图/引用不分页 */
}
img {
  break-inside: avoid;
  max-width: 100%;                      /* 图片不溢出页边 */
  height: auto;
}
```

### 2.4 寡行/孤行控制

```css
p {
  orphans: 3;                           /* 页底至少留 3 行 */
  widows: 3;                            /* 页顶至少留 3 行 */
}
```

---

## 3. 印刷排版字号系统

### 3.1 单位选择

| 单位 | 用途 | 说明 |
|---|---|---|
| `pt` | 正文字号 | 1pt = 1/72in,印刷标准单位。正文 ≥ 11pt |
| `mm` / `cm` | 页边距、物理尺寸 | 直观对应纸张 |
| `em` / `rem` | 标题比例、间距 | 相对字号缩放 |
| `px` | **避免用于印刷** | 屏幕单位,打印时 96px=1in 但易出错 |

### 3.2 推荐字号阶梯(正文 11pt 基准)

```css
:root {
  --font-body: 11pt;
  --font-small: 9pt;        /* 页眉页脚、caption */
  --font-h6: 11pt;
  --font-h5: 12pt;
  --font-h4: 13pt;
  --font-h3: 15pt;
  --font-h2: 18pt;
  --font-h1: 28pt;          /* H1/正文 ≈ 2.5×,满足层级比 */
  --font-display: 40pt;     /* 封面大标题 */
  --line-height: 1.6;       /* 衬线正文 1.5-1.7 */
}
```

### 3.3 不同场景的字号基准

| 文档类型 | 正文字号 | 行高 | 适合 |
|---|---|---|---|
| 技术报告 | 11pt | 1.5 | 默认,信息密度适中 |
| 长篇电子书 | 12pt | 1.65 | 阅读舒适,页数多 |
| 学术论文 | 10pt | 1.5 | 双栏,密度高 |
| 产品手册 | 11pt | 1.6 | 平衡 |
| 杂志长文 | 11pt | 1.7 | 阅读体验优先 |

---

## 4. 字体加载策略

### 4.1 衬线体优先(长文本)

打印介质**优先衬线体**,屏幕阅读疲劳低于无衬线。Web 端 Inter/Roboto 的"现代感"在 PDF 里读起来像 demo。

```css
body {
  font-family: "Source Serif Pro", "Noto Serif CJK SC", "Songti SC", serif;
}
```

### 4.2 中文字体回退链

```css
font-family: "Source Serif Pro",           /* 拉丁正文 */
             "Noto Serif CJK SC",           /* 思源宋体(跨平台) */
             "Songti SC", "SimSun",         /* macOS / Windows 宋体 */
             serif;
```

无衬线场景(标题/UI):
```css
font-family: "Söhne", "Helvetica Neue", "PingFang SC", "Microsoft YaHei", sans-serif;
```

### 4.3 等宽字体(代码块)

```css
code, pre {
  font-family: "JetBrains Mono", "Cascadia Code", "Consolas", "Source Code Pro", monospace;
  font-size: 0.9em;                        /* 略小于正文 */
}
```

### 4.4 Google Fonts 嵌入(网络可访问时)

```html
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Source+Serif+Pro:ital,wght@0,400;0,600;1,400&family=JetBrains+Mono:wght@400;500&display=swap">
```

> Playwright 渲染时 `wait_until='networkidle'` 会等字体加载。离线环境用系统字体回退链。

### 4.5 字体选择禁忌(借鉴 web-design-engineer)

| 禁用 | 原因 |
|---|---|
| Inter / Roboto / Arial / system-ui 当正文 | AI 默认,读起来像"生成的报告" |
| Fraunces | 过度使用 |
| 超过 3 个字体族 | 视觉混乱 |

---

## 5. 图片处理

### 5.1 路径解析(脚本内部)

| 路径形式 | 处理 |
|---|---|
| `http://` / `https://` | 保留,Playwright `networkidle` 等加载 |
| 相对路径 `images/x.jpg` | 相对 MD 文件目录解析 |
| 绝对路径 `D:\...` 或 `/...` | 直接使用,转 `file://` |
| data URI | 直接嵌入 |

### 5.2 CSS 约束

```css
img {
  max-width: 100%;                        /* 不超页边 */
  height: auto;
  break-inside: avoid;                    /* 不分页 */
  page-break-inside: avoid;
}
figure {
  break-inside: avoid;
  margin: 1.5em 0;
  text-align: center;
}
figcaption {
  font-size: var(--font-small);
  color: #666;
  margin-top: 0.5em;
  font-style: italic;
}
```

### 5.3 大图缩放

```css
img.full-page {
  max-height: 200mm;                      /* 留出页边距后最大高度 */
  width: auto;
}
```

---

## 6. 表格与代码块

### 6.1 表格

```css
table {
  break-inside: auto;                     /* 长表允许分页 */
  width: 100%;
  border-collapse: collapse;
  font-size: var(--font-body);
}
thead { display: table-header-group; }    /* 分页时每页重复表头 */
tr { break-inside: avoid; }               /* 单行不分页 */
th, td {
  border: 0.5pt solid #E2E2E2;
  padding: 6pt 8pt;
  text-align: left;
  vertical-align: top;
}
th {
  background: #F5F5F5;
  font-weight: 600;
}
```

### 6.2 代码块

```css
pre {
  break-inside: avoid;                    /* 短代码块不分页 */
  background: #F7F7F7;
  border: 0.5pt solid #E2E2E2;
  border-radius: 3px;                     /* 印刷用小圆角,不用 12px */
  padding: 12pt;
  font-size: 0.9em;
  line-height: 1.45;
  overflow-wrap: break-word;
  white-space: pre-wrap;                  /* 超长行换行,不溢出 */
}
code {
  font-family: "JetBrains Mono", monospace;
  background: #F0F0F0;
  padding: 1pt 3pt;
  border-radius: 2px;
}
pre code { background: none; padding: 0; }
```

> 长代码块(>40 行)允许分页,改用 `break-inside: auto` + 顶部底部加边框区分。

---

## 7. 目录(TOC)生成

### 7.1 CSS 计数器法(Playwright 支持 `target-counter`)

```css
.toc a::after {
  content: target-counter(attr(href), page);
  float: right;
}
.toc li { break-inside: avoid; }
```

### 7.2 手动占位法(兼容性更稳)

脚本生成 TOC 时,页码用 `[p.??]` 占位,PDF 渲染后由脚本回填——但 Playwright 一次性渲染无法回填。**推荐用 `target-counter`**,Chromium 打印支持。

### 7.3 TOC 排版

```css
.toc {
  break-after: page;                      /* TOC 单独成页 */
  page: toc;
}
.toc h1 { break-before: avoid; }          /* TOC 标题不强制分页 */
.toc ul { list-style: none; padding-left: 0; }
.toc-level-1 { font-weight: 600; margin-top: 8pt; }
.toc-level-2 { padding-left: 1.5em; font-weight: 400; }
.toc-level-3 { padding-left: 3em; font-size: 0.95em; color: #666; }
```

---

## 8. 颜色管理

### 8.1 印刷友好配色原则

- **大面积背景用浅色**(#FFFFFF / #F7F7F7 / #F1ECDE),避免大面积深色(费墨、易透背)
- **文字用深色**(#1A1A1A / #121212),不用纯黑 #000(对比过强)
- **强调色小面积使用**(≤ 5% 像素),如页眉、kicker、链接
- **避免霓虹色**(#00FF00 等),印刷偏色严重

### 8.2 CSS 变量管理

```css
:root {
  --color-ink: #1A1A1A;
  --color-ground: #FFFFFF;
  --color-surface: #F7F7F7;
  --color-secondary: #666666;
  --color-hairline: #E2E2E2;
  --color-accent: #D0021B;                /* 模板自包含 CSS 里改为硬编码 */
}
body { background: var(--color-ground); color: var(--color-ink); }
```

### 8.3 链接处理

```css
a {
  color: var(--color-ink);                /* 印刷时链接不用蓝色 */
  text-decoration: underline;
}
a::after {                                /* 可选:打印时显示 URL */
  content: " (" attr(href) ")";
  font-size: 0.85em;
  color: var(--color-secondary);
  word-break: break-all;
}
```

---

## 9. 封面设计

```css
.cover-page {
  page: cover;
  break-after: page;
  height: 297mm;                          /* A4 全高 */
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 60mm 30mm;
  text-align: center;
}
.cover-page h1 {
  font-size: var(--font-display);
  break-before: avoid;
  margin-bottom: 0.3em;
}
.cover-page .subtitle {
  font-size: 16pt;
  font-style: italic;
  color: var(--color-secondary);
  margin-bottom: 2em;
}
.cover-page .author {
  font-size: 12pt;
  margin-top: 4em;
}
```

---

## 10. 多栏布局(杂志/报纸风格)

```css
.multi-col-2 {
  column-count: 2;
  column-gap: 8mm;
  column-rule: 0.5pt solid var(--color-hairline);
}
.multi-col-3 {
  column-count: 3;
  column-gap: 6mm;
}
```

> 仅 `report-paper` 模板用双栏(学术论文)。其他模板默认单栏。

---

## 11. Playwright 渲染注意事项

### 11.1 已验证参数

```python
await page.goto(f"file://{html_path}", wait_until="networkidle")
await page.wait_for_timeout(1000)         # 等字体/图表渲染
await page.pdf(
    path=output_path,
    format="A4",                          # 或 width/height 显式指定
    print_background=True,                # 保留背景色
    margin={"top": "0", "right": "0", "bottom": "0", "left": "0"},  # @page 已管边距
    prefer_css_page_size=True,            # 用 CSS @page size 而非 format
)
```

### 11.2 `prefer_css_page_size=True` 的意义

让 Playwright 优先使用 CSS `@page { size: A4 }`,而非 `format="A4"`。这样模板里的 `@page` 配置(边距、页眉页脚)才生效。

### 11.3 网络图片超时

`networkidle` 默认等 500ms 无网络请求。若图片源慢,加 `wait_for_timeout(2000)`。失败时图片区域空白,不影响 PDF 生成。

---

## 12. 速查:打印 CSS 检查清单

- [ ] `@page` 定义了 size + margin + 页眉页脚
- [ ] 封面用 `@page :first { margin: 0 }` 或命名页
- [ ] `h1` 强制 `break-before: page`
- [ ] `h2-h6` 设 `break-after: avoid`
- [ ] `pre/table/figure/img` 设 `break-inside: avoid`(长表除外)
- [ ] 正文 ≥ 11pt,行高 1.5-1.7
- [ ] 字体回退链含中文字体
- [ ] `img { max-width: 100% }`
- [ ] `thead { display: table-header-group }`(分页重复表头)
- [ ] `orphans: 3; widows: 3`
- [ ] 大面积背景为浅色
- [ ] Playwright 用 `prefer_css_page_size=True`
