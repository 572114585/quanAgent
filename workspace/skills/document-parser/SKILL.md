---
name: "document-parser"
description: "Parse documents (PDF, Word, PPT, Excel, images) to Markdown using MinerU API. Invoke when user needs to extract text/tables/formulas from documents or convert files to Markdown. Uses precision API first, falls back to lightweight agent API."
allowed-tools: execute read_file write_file
---

# Document Parser (MinerU) Skill

Parse PDF, Word, PPT, Excel, and image documents into structured Markdown using the MinerU API. The skill implements a two-tier fallback strategy: first attempts the 🎯 Precision Extract API (vlm model, high accuracy, supports up to 200MB/200 pages), and if that fails, falls back to the ⚡ Agent Lightweight Extract API (no token required, up to 10MB/20 pages).

## ⚠️ 必须遵守的命令格式（违反会被 runtime 拦截或命令直接失败）

1. **命令必须单行**：`execute(command=...)` 的 command 是**单行字符串**，禁止用反斜杠 `\` + 换行、或裸换行续行。长命令就在一行内写完。

2. **中文 / JSON 用双引号包裹，内部转义双引号用 `\"`**：例如 `--options "{\"language\":\"ch\"}"`。

3. **只调用 skills 自带脚本**（`parse.py`）。**禁止 `write_file` 自写 `.py` 再 `execute` 跑**——runtime 对 python 脚本做了白名单校验，自写脚本会被 `[E_SHELL_DENIED]` 拦截。

4. **输出只写 `output/`**：runtime 限制 `write_file`/`edit_file` 只能写 `output/` 子树，`skills/` 目录只读。

## Script path

The agent's working directory is `workspace/`. Use **relative** script path:

```
skills/document-parser/scripts/parse.py
```

Run `python skills/document-parser/scripts/parse.py --help` first to see the exact flags.

## Usage

### Parse a document from URL

```bash
execute(command="python skills/document-parser/scripts/parse.py --url https://example.com/document.pdf --out output/document.md")
```

### Parse a local file (uploads to MinerU first)

```bash
execute(command="python skills/document-parser/scripts/parse.py --file uploads/document.pdf --out output/document.md")
```

### Optional parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| `--url` | Remote document URL to parse | - |
| `--file` | Local file path to parse (relative to workspace) | - |
| `--out` | Output Markdown file path (required, e.g. output/doc.md) | - |
| `--language` | Document language (ch/en/ja/ko/fr/de/es/ru/ar/it/pt) | ch |
| `--model` | Precision API model version: pipeline, vlm, MinerU-HTML | vlm |
| `--enable-table` | Enable table recognition | true |
| `--enable-formula` | Enable formula recognition | true |
| `--is-ocr` | Enable OCR (for scanned documents) | false |
| `--page-range` | Page range for PDF, e.g. "1-10" or "5" | - |
| `--no-fallback` | Disable fallback to Agent Lightweight API | false |
| `--poll-interval` | Polling interval in seconds | 3 |
| `--timeout` | Maximum wait time in seconds | 300 |

You must provide either `--url` or `--file`, but not both.

### Examples

Parse a PDF URL with OCR enabled:

```bash
execute(command="python skills/document-parser/scripts/parse.py --url https://example.com/scanned.pdf --out output/scanned.md --is-ocr true")
```

Parse a local Word document with Chinese language:

```bash
execute(command="python skills/document-parser/scripts/parse.py --file uploads/report.docx --out output/report.md --language ch")
```

Parse pages 1-5 of a PDF without fallback:

```bash
execute(command="python skills/document-parser/scripts/parse.py --url https://example.com/doc.pdf --out output/doc.md --page-range 1-5 --no-fallback true")
```

## Fallback Strategy

1. **First attempt**: 🎯 Precision Extract API (vlm model) — highest accuracy, supports tables/formulas, up to 200MB/200 pages, requires token.
2. **On failure**: ⚡ Agent Lightweight Extract API — no token required, IP rate-limited, up to 10MB/20 pages, Markdown only output.
3. **If both fail**: Returns an error message describing the failure.

The script prints which API was used and the result status. If the precision API succeeds, the ZIP result is downloaded and extracted:
- `full.md` is saved to the specified `--out` path (e.g. `output/document.md`)
- All images from the document are extracted to `output/images/` directory (or the same relative structure as in the ZIP), preserving Markdown relative image references like `![img](images/xxx.jpg)`
- If the agent API succeeds, the Markdown is downloaded directly from the CDN URL (images remain on CDN as absolute URLs).

When reading the parsed Markdown, images will be available at relative paths like `output/images/xxx.jpg` — you can reference them directly or describe them to the user.

## Supported File Types

- Precision API: PDF, DOC, DOCX, PPT, PPTX, XLS, XLSX, Images (png/jpg/jpeg/jp2/webp/gif/bmp), HTML
- Agent API: PDF, DOCX, PPTX, XLSX, Images (png/jpg/jpeg/jp2/webp/gif/bmp)
