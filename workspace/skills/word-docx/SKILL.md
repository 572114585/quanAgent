---
name: word-docx
description: "Create, inspect, and edit Word documents (.docx). Use whenever the task involves Word files, headings/paragraphs/tables, or round-trip editing that must preserve formatting. Ships helper scripts so you call them instead of hand-writing python-docx code."
allowed-tools: execute read_file write_file
---

# Word (DOCX) Skill

Create, inspect, and edit Word documents via the bundled scripts. Each script is
self-contained and uses `python-docx` internally — you do **not** write
`python-docx` code yourself. Call the scripts with the `execute` tool.

## ⚠️ 必须遵守的命令格式（违反会被 runtime 拦截或命令直接失败）

1. **命令必须单行**：`execute(command=...)` 的 command 是**单行字符串**，禁止用
   反斜杠 `\` + 换行、或裸换行续行。cmd.exe 会把换行后的参数（`--out`/`--blocks`
   等）当成新命令，导致 argparse 报 `the following arguments are required: --out`。
   长命令就在一行内写完。

2. **中文 / JSON 用双引号包裹，内部转义双引号用 `\"`**：
   `--blocks "[{\"type\":\"heading\",\"level\":1,\"text\":\"一、简介\"}]"`。
   禁止在 JSON 字符串值里用中文弯引号 `"..."`（与 Python/JSON 的 `"` 冲突）。

3. **只调用 skills 自带脚本**（`create.py`/`edit.py`/`view.py`）。
   **禁止 `write_file` 自写 `.py` 再 `execute` 跑**——runtime 对 python 脚本做了
   白名单校验，自写脚本会被 `[E_SHELL_DENIED]` 拦截。

4. **输出只写 `output/`**：runtime 限制 `write_file`/`edit_file` 只能写 `output/`
   子树，`skills/` 目录只读（写 skills 会被 `[E_SHELL_DENIED]` 拦截）。

## Script paths

The `execute` tool's working directory is the workspace root, so call the
scripts with paths relative to it:

```
skills/word-docx/scripts/create.py
skills/word-docx/scripts/edit.py
skills/word-docx/scripts/view.py      ← inspect/verify (named "view", not "inspect", to avoid a stdlib clash)
```

Both `skills/word-docx/...` (relative) and `/skills/word-docx/...` (virtual
absolute) forms work — the runtime normalizes either to the right path before
executing. Prefer the relative form (`skills/...`); it is unambiguous and works
even if path normalization were ever disabled.

Run `python <script> --help` first to see the exact flags. Output files go
under `output/` (relative), e.g. `output/report.docx`.

## Workflow

1. **Create** the document with `create.py`.
2. **Inspect** it with `view.py` to verify (always do this).
3. **Edit** it with `edit.py` only if the user later asks for changes.

### Step 1 — Create a document

```bash
execute(command="python skills/word-docx/scripts/create.py --help")
```

Typical call (batch mode — all headings first, then all paragraphs):

```bash
execute(command="python skills/word-docx/scripts/create.py \
  --out output/report.docx \
  --title 'Project Report' \
  --headings '[{\"level\":1,\"text\":\"Overview\"},{\"level\":2,\"text\":\"Goals\"}]' \
  --paragraphs '[\"This report covers the Q2 work.\",\"See the table below.\"]' \
  --bullets '[\"Goal one\",\"Goal two\",\"Goal three\"]' \
  --table '{\"headers\":[\"Metric\",\"Value\"],\"rows\":[[\"Users\",\"1,200\"],[\"Revenue\",\"$9.9k\"]]}')
```

- `--title` is a top-level Heading 1.
- `--headings` is a JSON array of `{level, text}` (level 1–9).
- `--paragraphs` is a JSON array of body paragraph strings.
- `--bullets` is a JSON array written as bullet list items (`List Bullet` style).
- `--table` is a JSON object `{headers:[...], rows:[[...],...]}`.

> **Batch-mode limitation**: in batch mode (`--headings/--paragraphs/--bullets`),
> ALL headings are added first, then ALL paragraphs, then ALL bullets — so you
> cannot interleave a heading with the paragraph that belongs to it. For a
> multi-section document where each heading is followed by its own body text,
> use `--blocks` instead (next subsection).

#### `--blocks` — interleaved content in one call (preferred for multi-section docs)

`--blocks` takes a JSON array of content blocks written **in the order you give
them**, so a heading can be followed immediately by its paragraph, then the
next heading, and so on — no need to call create.py once per section or to
fall back to writing your own python-docx script. Each block has a `type`:

| type        | fields                                   |
|-------------|------------------------------------------|
| `heading`   | `level` (1–9), `text`                    |
| `paragraph` | `text`                                   |
| `bullet`    | `text`                                   |
| `table`     | `headers:[...]`, `rows:[[...],...]`      |

```bash
execute(command="python skills/word-docx/scripts/create.py \
  --out output/report.docx \
  --title 'Project Report' \
  --blocks '[{\"type\":\"heading\",\"level\":1,\"text\":\"Overview\"},{\"type\":\"paragraph\",\"text\":\"This report covers the Q2 work.\"},{\"type\":\"heading\",\"level\":2,\"text\":\"Goals\"},{\"type\":\"bullet\",\"text\":\"Goal one\"},{\"type\":\"bullet\",\"text\":\"Goal two\"},{\"type\":\"table\",\"headers\":[\"Metric\",\"Value\"],\"rows\":[[\"Users\",\"1,200\"]]}]')
```

When `--blocks` is set, `--headings/--paragraphs/--bullets/--table` are ignored
(a warning is printed). `--title` is still honored and added first.

### Step 2 — Inspect (verify before reporting)

```bash
execute(command="python skills/word-docx/scripts/view.py --file output/report.docx")
```

Add `--show-styles` to see the paragraph style name next to each line, and
`--max-paragraphs 20` for more content.

### Step 3 — Edit an existing document (optional)

```bash
execute(command="python skills/word-docx/scripts/edit.py --help")
```

- `--append-paragraphs '["New paragraph."]'` appends body paragraphs.
- `--add-heading '{"level":2,"text":"Next Steps"}'` appends a heading (repeatable).
- `--append-bullets '["Step 1","Step 2"]'` appends bullet items.
- `--append-blocks '[{"type":"heading","level":2,"text":"Notes"},{"type":"paragraph","text":"..."}]'`
  appends an interleaved heading+body section in one call — same block format as
  create.py's `--blocks`. Use this instead of multiple `--add-heading` /
  `--append-paragraphs` calls when adding a section whose heading and body must
  stay together.
- `--replace '{"find":"old","with":"new"}'` does find-and-replace across runs
  (repeatable; handles text split across multiple runs).

### Step 4 — Report

Tell the user the file path, paragraph/table counts, and heading outline.

## Key Rules (when you must work beyond the scripts)

- **Never hand-write python-docx code** — that is exactly what the scripts are
  for. If a single document needs interleaved heading+body sections, use
  `create.py --blocks` (or `edit.py --append-blocks`) to produce it in one call.
  Only drop to raw `python-docx` if the scripts genuinely cannot express what
  you need (and even then, prefer extending a script over a throwaway script).
- **Use real Heading styles**: `Heading 1`/`Heading 2`…, not bold+large font.
  The scripts do this; only override if you must match a custom style.
- **Lists use styles**: bullets via `List Bullet`, numbers via `List Number`.
  Don't fake bullets with "• " prefixes.
- **Tables**: set column widths explicitly when layout matters; the scripts use
  a plain table — restyle if the user needs borders/shading.
- **Minimal edits on reviewed docs**: when a doc has tracked changes, replace
  only the target text, never rewrite whole paragraphs.
- **One phrase may span multiple runs**: simple text replacement can fail; the
  `--replace` in `edit.py` reconstructs run text so it works across splits.

## Common Traps

- **Batch-mode ordering**: `--headings/--paragraphs/--bullets` add each group
  in full before the next, so a heading and its paragraph end up separated.
  Use `--blocks` whenever section order matters.
- Copy-paste between documents can import unwanted styles and numbering.
- Empty paragraphs used as spacing make templates fragile — prefer paragraph
  spacing settings.
- Table auto-fit looks fine in Word but drifts in Google Docs / LibreOffice.
- Restarting numbered lists manually usually fails — numbering state lives
  outside paragraph text. If the user needs controlled list restarting, mention
  this limitation.
