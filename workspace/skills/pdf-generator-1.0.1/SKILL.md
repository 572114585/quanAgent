---
name: pdf-generator
description: "创建、查看、合并、拆分、编辑 PDF 文档。支持从 Markdown/HTML/JSON 生成，支持标题/段落/列表/表格/图片嵌入，跨平台纯 Python 实现（无系统依赖），支持中文。"
allowed-tools: execute read_file write_file
---

# PDF Generator 技能

通过自带的脚本创建、查看和编辑 PDF 文档。每个脚本都是自包含的，内部使用 `fpdf2` 和 `pypdf`——你**不需要**自己写 PDF 相关代码，直接用 `execute` 工具调用脚本即可。

## ⚠️ 必须遵守的命令格式（违反会被 runtime 拦截或命令直接失败）

1. **命令必须单行**：`execute(command=...)` 的 command 是**单行字符串**，禁止用反斜杠 `\` + 换行、或裸换行续行。cmd.exe 会把换行后的参数当成新命令，导致 argparse 报错。长命令就在一行内写完。

2. **中文 / JSON 用双引号包裹，内部转义双引号用 `\"`**：
   `--blocks "[{\"type\":\"heading\",\"level\":1,\"text\":\"一、项目概述\"}]"`。
   禁止在 JSON 字符串值里用中文弯引号 `"..."`（与 Python/JSON 的 `"` 冲突）。

3. **只调用 skills 自带脚本**（`create.py`/`edit.py`/`view.py`）。
   **禁止 `write_file` 自写 `.py` 再 `execute` 跑**——runtime 对 python 脚本做了白名单校验，自写脚本会被 `[E_SHELL_DENIED]` 拦截。

4. **输出只写 `output/`**：runtime 限制 `write_file`/`edit_file` 只能写 `output/` 子树，`skills/` 目录只读。

## 脚本路径

`execute` 工具的工作目录是 workspace 根目录，用相对路径调用脚本：

```
skills/pdf-generator-1.0.1/scripts/create.py
skills/pdf-generator-1.0.1/scripts/view.py
skills/pdf-generator-1.0.1/scripts/edit.py
```

先运行 `python <script> --help` 查看完整参数。输出文件放在 `output/` 目录下，例如 `output/report.pdf`。

## 工作流程

1. **创建** PDF 用 `create.py`。
2. **验证** 用 `view.py` 查看生成结果（必须做这一步）。
3. **编辑** 用 `edit.py` 合并、拆分、添加水印或修改元数据（按需使用）。

### 第一步 — 创建 PDF

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/create.py --help")
```

典型调用（使用 `--blocks` 按顺序生成混合内容，推荐用于多章节文档）：

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/create.py --out output/report.pdf --title '项目报告' --author '张三' --blocks '[{\"type\":\"heading\",\"level\":1,\"text\":\"概述\"},{\"type\":\"paragraph\",\"text\":\"本文档介绍Q2工作进展。\"},{\"type\":\"heading\",\"level\":2,\"text\":\"目标\"},{\"type\":\"bullet\",\"text\":\"目标一\"},{\"type\":\"bullet\",\"text\":\"目标二\"},{\"type\":\"table\",\"headers\":[\"指标\",\"数值\"],\"rows\":[[\"用户数\",\"1,200\"],[\"收入\",\"9.9万元\"]]}]'")
```

- `--title`：文档标题（同时作为页眉和一级标题）。
- `--author`：文档作者元数据。
- `--page-size`：页面大小，支持 A4/Letter/Legal，默认 A4。
- `--blocks`：JSON 数组，按给定顺序输出内容块，支持的类型：

| type        | 字段                                     |
|-------------|------------------------------------------|
| `heading`   | `level` (1-6), `text`                    |
| `paragraph` | `text`                                   |
| `bullet`    | `text`                                   |
| `table`     | `headers:[...]`, `rows:[[...],...]`      |
| `image`     | `path` (图片文件路径，支持 JPG/PNG)       |

简单文档也可以用批量模式参数（先输出所有标题，再所有段落，再所有列表）：

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/create.py --out output/simple.pdf --title '简单报告' --headings '[{\"level\":1,\"text\":\"简介\"}]' --paragraphs '[\"这是正文第一段。\"]' --bullets '[\"要点一\",\"要点二\"]' --table '{\"headers\":[\"A\",\"B\"],\"rows\":[[\"1\",\"2\"]]}'")
```

也可以直接从 HTML 内容或文件生成（支持基础 HTML 标签）：

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/create.py --out output/from_html.pdf --title 'HTML文档' --html '<h1>标题</h1><p>段落内容</p>'")
```

### 从 Markdown 文件生成（支持图片嵌入）

使用 `--md-file` 从 Markdown 文件生成 PDF，支持标准 Markdown 语法和图片：

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/create.py --out output/from_md.pdf --title 'Markdown文档' --md-file output/doc.md")
```

也可以直接传入 Markdown 内容字符串：

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/create.py --out output/from_md_str.pdf --markdown '# 标题\n\n这是段落内容。\n\n![图片说明](output/images/photo.jpg)'")
```

**Markdown 支持的元素：**
- 标题：`# H1` 到 `###### H6`
- 段落：普通文本，自动换行
- 粗体/斜体：`**粗体**` `*斜体*`
- 无序列表：`- 项目` 或 `* 项目`
- 有序列表：`1. 项目`
- 代码块：` ```code``` `
- 引用：`> 引用文本`
- 分隔线：`---` 或 `***`
- 表格：标准 Markdown 表格语法
- **图片：`![alt](path/to/image.jpg)`** - 支持 JPG/PNG 格式

**图片路径说明：**
- 相对路径：相对于 Markdown 文件所在目录，如 `images/photo.jpg`
- Web 风格路径：以 `/` 开头的路径会自动搜索 workspace/output 等目录，如 `/output/images/photo.jpg`
- 绝对路径：Windows 完整路径如 `D:\\project\\images\\photo.jpg`
- `--workspace` 参数：可显式指定工作区根目录以帮助解析相对路径

**`--blocks` 模式中的图片块：**
```json
{"type": "image", "path": "output/images/chart.png"}
```

### 第二步 — 验证（汇报给用户前必做）

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/view.py --file output/report.pdf")
```

加 `--extract-text` 可以提取文本内容验证，`--max-pages 5` 控制提取页数，`--show-metadata` 显示完整元数据。

### 第三步 — 编辑已有 PDF（可选）

```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/edit.py --help")
```

支持四种操作（四选一）：

**合并多个 PDF：**
```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/edit.py --merge --files '[\"output/a.pdf\",\"output/b.pdf\"]' --out output/merged.pdf")
```

**拆分/提取页面：**
```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/edit.py --split --file output/merged.pdf --pages '0,2' --out output/pages_1_3.pdf")
```
`--pages` 支持 0 基索引，逗号分隔如 `0,2,4`，也支持范围如 `0:5`（前5页）。

**修改元数据（标题/作者/主题）：**
```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/edit.py --meta --file output/report.pdf --title '新标题' --author '李四' --out output/updated.pdf")
```

**添加文字水印：**
```bash
execute(command="python skills/pdf-generator-1.0.1/scripts/edit.py --watermark --file output/report.pdf --text '机密文件' --watermark-opacity 0.2 --out output/watermarked.pdf")
```

### 第四步 — 汇报

告诉用户文件路径、页数、文件大小，以及包含的内容类型（标题、段落、列表、表格数量）。

## 核心规则（超出脚本能力时必须遵守）

- **永远不要手写 fpdf2/pypdf 代码**——这正是脚本存在的意义。如果单个文档需要交错的标题+正文结构，用 `create.py --blocks` 一次性生成。
- **中文支持**：脚本自动检测并使用系统中文字体（Windows 微软雅黑/黑体/宋体，macOS 苹方，Linux 文泉驿/Noto CJK）。
- **输出验证**：创建后必须用 `view.py` 检查文件大小（0 字节说明失败）和页数。
- **页面设置**：默认 A4 纸张，自动分页，自动页码。
- **表格**：表格自动等宽分布，表头有灰色背景加粗。

## 常见陷阱

- **批量模式顺序问题**：`--headings/--paragraphs/--bullets` 会先输出全部标题再全部段落，所以标题和它对应的正文会被分开。需要交错结构请用 `--blocks`。
- **路径参数问题**：所有路径都是 workspace 相对路径，输出必须在 `output/` 目录。支持多种路径格式：相对路径、web 风格 `/` 开头路径、绝对路径。
- **JSON 转义**：Windows cmd.exe 下单引号不会被当作引号，所以 JSON 必须用双引号，内部双引号用 `\"` 转义。
- **HTML 支持有限**：`--html` 支持基础 HTML 标签（h1-h6/p/ul/ol/li/table/b/i/u/br/img 等），复杂 CSS 样式不支持。
- **Markdown 图片语法**：必须使用标准 Markdown 图片语法 `![alt](path)`，HTML 注释 `<!-- image-->` 不会被识别为图片。
- **依赖缺失**：确保已安装 `fpdf2` 和 `Pillow`：`pip install fpdf2 Pillow`。fpdf2 是 PDF 生成核心库，Pillow 用于图片尺寸检测。
- **图片格式**：支持 JPG/JPEG 和 PNG 格式。PNG 透明通道会自动转换为白色背景。
