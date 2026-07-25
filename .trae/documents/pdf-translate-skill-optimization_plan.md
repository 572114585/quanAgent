# PDF翻译流程优化计划

## 问题与根因

### 问题1：翻译后图片标记丢失

**现象**：MinerU提取的MD带有 `![](...)` 图片引用，但Agent(LLM)翻译后图片标记消失。

**根因**：Agent直接翻译MD内容时，没有明确的规则要求保留图片引用。SYSTEM_PROMPT中没有任何关于"翻译/改写MD时必须保留图片标记"的指导，LLM默认把图片引用当成无关内容丢弃。

**修改位置**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) 的 SYSTEM_PROMPT

### 问题2：表格超出文字排版

**现象**：论文中的实验数据表格在PDF中溢出版心。

**根因**：component-catalog.md中的表格组件(T1/T2/T3)都缺少防溢出CSS：
- 没有 `table-layout: fixed`（固定列宽，防内容撑开表格）
- 没有 `word-wrap: break-word`（单元格文字不换行导致溢出）
- 没有宽表格自动跨双栏机制（双栏布局中宽表格被挤在一栏里）
- paper/sample.html的table样式同样缺少这些规则

**修改位置**：
- [workspace/skills/md-to-pdf/references/component-catalog.md](file:///d:/project/workspace/skills/md-to-pdf/references/component-catalog.md)
- [workspace/skills/md-to-pdf/references/showcase/paper/sample.html](file:///d:/project/workspace/skills/md-to-pdf/references/showcase/paper/sample.html)
- [workspace/skills/md-to-pdf/SKILL.md](file:///d:/project/workspace/skills/md-to-pdf/SKILL.md)

### 问题3：中间产物过多展示给用户

**现象**：用户只需要最终PDF，但Agent把提取的MD、图片、HTML中间产物等都作为结果汇报给了用户。

**根因**：SYSTEM_PROMPT虽有 output/ vs tmp/ 的目录约定，但没有"任务开始时声明最终产物 + 任务完成时只展示最终产物"的规则。Agent把所有写到 output/ 的文件都当作交付物汇报了。

**修改位置**：[agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) 的 SYSTEM_PROMPT

---

## 修改清单

| 文件 | 操作 | 改什么 |
|------|------|--------|
| `agent_core/prompts.py` | 修改 | SYSTEM_PROMPT 增加两条规则：①翻译/改写MD时必须保留图片引用 ②任务开始时声明最终产物、完成时只展示最终产物 |
| `workspace/skills/md-to-pdf/references/component-catalog.md` | 修改 | 现有T1/T2/T3表格组件补充防溢出CSS；新增T4自适应防溢出表格组件 |
| `workspace/skills/md-to-pdf/references/showcase/paper/sample.html` | 修改 | table样式补充防溢出规则 |
| `workspace/skills/md-to-pdf/SKILL.md` | 修改 | Step 3渲染HTML部分增加表格防溢出指导 |

---

## 详细修改内容

### 修改1：SYSTEM_PROMPT 增加翻译保留图片规则

在 `agent_core/prompts.py` 的 SYSTEM_PROMPT "通用编排原则"部分，新增一条规则：

```
- **翻译/改写 MD 时保留结构标记**：当翻译或改写 Markdown 内容时，必须原样保留所有结构性标记，特别是 `![](...)` 图片引用、表格 `|...|` 结构、代码块、公式 `$...$`/`$$...$$`。翻译只改文字内容，不改结构。翻译完成后必须自检：数一下 `![](` 出现次数，翻译后不得少于翻译前。图片路径一个字符都不许改，只翻译 alt 文本。禁止用 `[image: xxx]` 等文字占位符替换真实图片引用。
```

### 修改2：SYSTEM_PROMPT 增加产物声明与展示规则

在 "文件输出目录约定"部分之后，新增一节：

```
## 产物声明与展示规则
- **任务开始时声明产物**：接到任务后，先分析用户真正需要什么交付物，在回复中明确声明"本轮最终产物是 xxx"，中间产物写到 tmp/ 不作为交付。
- **任务完成时只展示最终产物**：汇报结果时，只列出声明的最终产物（路径+简要说明）。中间产物（提取的MD、HTML中间文件、临时图片等）不要作为结果展示给用户，即使用户可能看到文件列表。
- **示例**：用户说"把这个PDF翻译为中文并输出PDF"→ 声明最终产物为 `output/xxx-zh.pdf`，MinerU提取的MD/图片写 tmp/、翻译后的MD写 tmp/、HTML中间产物写 tmp/，最终只汇报 PDF 路径。
```

### 修改3：component-catalog.md 表格防溢出

在现有 T1/T2/T3 的 CSS 中补充通用防溢出规则，并新增 T4 组件：

**通用防溢出规则**（追加到现有表格CSS后）：
```css
/* 防溢出通用规则 */
table { table-layout: fixed; }
th, td { word-wrap: break-word; word-break: break-word; overflow-wrap: break-word; }
/* 宽表格跨双栏 */
.table-full-width { column-span: all; -webkit-column-span: all; }
/* 屏幕预览时横向滚动（不影响打印） */
@media screen { .table-wrapper { overflow-x: auto; } }
```

**新增 T4 自适应防溢出表格**：
```css
/* T4: 自适应防溢出表格 — 适合列多/内容长的实验数据表 */
table.adaptive { table-layout: fixed; width: 100%; border-collapse: collapse; margin: 1em 0; font-size: 8px; }
table.adaptive th { font-weight: 700; padding: 4px 6px; text-align: center; border-top: 2px solid #000; border-bottom: 2px solid #000; word-wrap: break-word; }
table.adaptive td { padding: 3px 6px; text-align: center; border-bottom: 1px solid #CCC; word-wrap: break-word; overflow-wrap: break-word; }
table.adaptive tr:last-child td { border-bottom: 2px solid #000; }
/* 列多时自动缩小 */
table.compact { font-size: 7px; }
table.compact th, table.compact td { padding: 2px 4px; }
```

HTML用法：
```html
<!-- 双栏内的窄表格 -->
<div class="no-break">
  <table class="adaptive">...</table>
</div>

<!-- 跨双栏的宽表格 -->
<div class="no-break table-full-width">
  <table class="adaptive compact">...</table>
</div>
```

### 修改4：paper/sample.html 表格样式更新

在现有 table CSS（第270-298行）中补充：
```css
table {
  width: 100%;
  table-layout: fixed;          /* 新增：固定布局 */
  border-collapse: collapse;
  margin: 1em 0;
  font-size: 9px;
}
th, td {
  word-wrap: break-word;        /* 新增：自动换行 */
  word-break: break-word;       /* 新增：长词断行 */
  overflow-wrap: break-word;    /* 新增：兼容性 */
}
/* 新增：宽表格跨双栏 */
table.full-width {
  column-span: all;
  -webkit-column-span: all;
}
```

### 修改5：md-to-pdf SKILL.md 增加表格防溢出指导

在 Step 3 "渲染 HTML" 部分的表格处理说明中，新增：

```markdown
#### 表格处理（关键：防溢出）

**问题**：列多或内容长的表格在双栏布局中会溢出版心。

**规则**：
- 所有表格必须加 `table-layout: fixed` + `word-wrap: break-word`
- 列数 ≤5 的表格放在双栏内，用 `.no-break` 防跨页
- 列数 >5 的宽表格用 `.table-full-width` 跨双栏显示
- 内容特别长的表格加 `.compact` 类缩小字号（8px → 7px）
- 表格包在 `<div class="no-break">` 中防跨页断裂
```

---

## 验证方案

1. **图片保留验证**：让Agent翻译一个带图片的MD，检查翻译后 `![](` 数量是否与原文一致
2. **表格防溢出验证**：用包含6列以上表格的论文渲染PDF，检查表格是否正常显示不溢出
3. **产物展示验证**：执行PDF翻译任务，检查Agent是否在开始时声明最终产物、结束时只展示PDF而不展示中间文件
