---
name: mineru
description: "MinerU 文档提取:把 PDF、扫描件、图片、Word/PPT/Excel、网页转为 Markdown/HTML/LaTeX/DOCX。优先使用高精度 extract(token 模式,支持多格式/大文件/VLM),失败自动降级 flash-extract(免 token,限 10MB/20 页),均失败则报错。支持 80+ 语言、表格/公式/OCR 识别。"
allowed-tools: execute read_file write_file
---

# MinerU 文档提取技能

通过自带的 `extract.py` 脚本调用 `mineru-open-api` CLI,把各类文档转为
Markdown 等格式。脚本内部实现**自动降级**:extract → flash-extract → 报错。

## ⚠️ 必须遵守的命令格式(违反会被 runtime 拦截或命令直接失败)

1. **命令必须单行**:`execute(command=...)` 的 command 是**单行字符串**,禁止用
   反斜杠 `\` + 换行、或裸换行续行。长命令就在一行内写完。

2. **路径用相对路径**:输入文件相对 workspace 根目录,如 `tmp/report.pdf`;
   输出文件必须落在 `output/` 子树,如 `output/result.md`。

3. **只调用 skills 自带脚本**(`extract.py`)。**禁止 `write_file` 自写 `.py`
   再 `execute` 跑**——runtime 对 python 脚本做了白名单校验,自写脚本会被
   `[E_SHELL_DENIED]` 拦截。

4. **输出只写 `output/`**:runtime 限制 `write_file`/`edit_file` 只能写 `output/`
   子树,`skills/` 目录只读。

## 脚本路径

`execute` 工具的工作目录是 workspace 根目录,用相对路径调用脚本:

```
skills/mineru/scripts/extract.py
```

先运行 `python skills/mineru/scripts/extract.py --help` 查看完整参数。
输出文件放在 `output/` 目录下,例如 `output/report.md`。

## 前置依赖

- **Node.js**(已在 runtime PATH 中)
- **mineru-open-api CLI**:`npm install -g mineru-open-api`(已全局安装则跳过)
- **MinerU token**(仅 extract 模式需要):在 `.env` 中设置
  `MINERU_API_TOKEN="你的token"`。token 获取:https://mineru.net/apiManage/token

## 降级策略(自动,无需手动干预)

| 优先级 | 模式 | token | 输出格式 | 限制 |
|--------|------|-------|----------|------|
| 1 | `extract` | 需要 | md/json/html/latex/docx | 200MB / 600 页 |
| 2 | `flash-extract` | 免 token | 仅 md | 10MB / 20 页 |
| 3 | 报错 | — | — | — |

- 有 token 时:先试 extract,失败则降级 flash-extract
- 无 token 时:直接走 flash-extract
- 均失败:输出错误汇总 + 排查建议,退出码 1
- 可用 `--mode extract` 强制只走 extract,`--mode flash` 强制只走 flash

## 工作流程

### 第一步 — 提取文档

```bash
execute(command="python skills/mineru/scripts/extract.py --help")
```

典型调用(从本地 PDF 提取 Markdown,自动降级):

```bash
execute(command="python skills/mineru/scripts/extract.py tmp/report.pdf -o output/report.md")
```

指定格式 + VLM 模型(extract 模式专用):

```bash
execute(command="python skills/mineru/scripts/extract.py tmp/report.pdf -o output/out/ -f md,html --model vlm")
```

从 URL 提取:

```bash
execute(command="python skills/mineru/scripts/extract.py https://example.com/doc.pdf -o output/url_result.md")
```

OCR 扫描件 + 指定页码:

```bash
execute(command="python skills/mineru/scripts/extract.py tmp/scanned.pdf -o output/scanned.md --ocr --pages 1-10")
```

强制只用 flash-extract(免 token 快速提取):

```bash
execute(command="python skills/mineru/scripts/extract.py tmp/small.pdf -o output/quick.md --mode flash")
```

### 参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `input` | 输入文件路径或 URL(必填) | — |
| `-o`/`--output` | 输出路径(文件或目录) | `output/` |
| `-f`/`--format` | 输出格式:md/json/html/latex/docx(逗号分隔;仅 extract 生效) | `md` |
| `--model` | extract 模型:vlm/pipeline/html | 自动 |
| `--language` | 文档语言 | `ch` |
| `--pages` | 页码范围,如 `1-10,15` | 全部 |
| `--ocr` | 启用 OCR(扫描件) | 关 |
| `--no-formula` | 禁用公式识别 | 默认开 |
| `--no-table` | 禁用表格识别 | 默认开 |
| `--timeout` | 单次调用超时秒数 | 900 |
| `--mode` | 强制模式:auto/extract/flash | auto |

### 第二步 — 验证结果

```bash
execute(command="python skills/mineru/scripts/extract.py tmp/report.pdf -o output/report.md")
```

成功时 stdout 输出结果路径,stderr 输出使用的模式(`extract` 或 `flash-extract`)。
失败时 stderr 输出错误汇总。

### 第三步 — 汇报

告诉用户:
- 实际使用的模式(extract / flash-extract)
- 输出文件路径
- 输出格式
- 如果发生了降级,说明降级原因

## 支持的输入格式

| 格式 | extract | flash-extract |
|------|:-------:|:-------------:|
| PDF (`.pdf`) | ✓ | ✓ |
| 图片 (`.png`/`.jpg`/`.jpeg`/`.webp`/`.bmp` 等) | ✓ | ✓ |
| Word (`.docx`) | ✓ | ✓ |
| Word (`.doc`) | ✓ | ✗ |
| PPT (`.pptx`) | ✓ | ✓ |
| PPT (`.ppt`) | ✓ | ✗ |
| Excel (`.xlsx`) | ✓ | ✓ |
| Excel (`.xls`) | ✓ | ✗ |
| HTML (`.html`) | ✓ | ✗ |
| URL(远程文件) | ✓ | ✓ |

## 支持的 `--language` 值

默认 `ch`(中英文)。常用值:`ch`/`en`/`japan`/`korean`/`chinese_cht`/`th`/`el`/
`ta`/`te`/`ka`,以及语系包 `latin`/`arabic`/`cyrillic`/`east_slavic`/`devanagari`。

## 常见陷阱

- **token 变量名**:`.env` 中为 `MINERU_API_TOKEN`(脚本会自动读取,无需手动传 `--token`)。
- **flash-extract 限制**:10MB / 20 页,超出会失败,需用 extract 模式。
- **网络依赖**:extract 和 flash-extract 均需访问 `mineru.net`,离线环境不可用。
- **大文件超时**:大 PDF 的 extract 可能较慢,可用 `--timeout 1800` 延长超时。
- **输出路径**:目录形式(如 `output/out/`)会保留多格式文件;文件形式(如 `output/r.md`)
  适合单格式。
