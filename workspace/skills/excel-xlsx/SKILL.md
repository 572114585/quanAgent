---
name: excel-xlsx
description: "Create, inspect, and edit Excel/XLSX workbooks. Use whenever the task involves .xlsx/.xls/.csv/.tsv, formulas, formatting, or workbook structure. Ships helper scripts so you call them instead of hand-writing openpyxl code."
allowed-tools: execute read_file write_file
---

# Excel (XLSX) Skill

Create, inspect, and edit Excel workbooks via the bundled scripts. Each script is
self-contained and uses `openpyxl`/`pandas` internally — you do **not** write
`openpyxl` code yourself. Call the scripts with the `execute` tool.

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

The agent's working directory is `workspace/`. Use **relative** script paths
(what you pass to `execute`):

```
skills/excel-xlsx/scripts/create.py
skills/excel-xlsx/scripts/edit.py
skills/excel-xlsx/scripts/view.py      ← inspect/verify (named "view", not "inspect", to avoid a stdlib clash)
```

Run `python <script> --help` first to see the exact flags, then run it. Output
files go under `output/`, e.g. `output/report.xlsx`.

## Workflow

1. **Create** the workbook with `create.py`.
2. **Inspect** it with `view.py` to verify (always do this).
3. **Edit** it with `edit.py` only if the user later asks for changes.

### Step 1 — Create a workbook

```bash
execute(command="python skills/excel-xlsx/scripts/create.py --help")
```

Typical call:

```bash
execute(command="python skills/excel-xlsx/scripts/create.py \
  --out output/sales.xlsx \
  --sheet 'Sales' \
  --title '2026 Q2 Sales' \
  --headers 'Product,Quantity,Unit Price,Total' \
  --rows '[\"Widget,10,9.9,=B2*C2\",\"Gadget,5,19.9,=B3*C3\"]' \
  --text-cols 'A' ")
```

- `--rows` is a JSON array of strings; each string is comma-separated cell values
  (use JSON quotes/escapes as shown). Cells starting with `=` are written as
  formulas.
- `--text-cols A,B` forces those columns to text — use for IDs, phone numbers,
  ZIP codes, and anything with leading zeros so they are not truncated.

### Step 2 — Inspect (verify before reporting)

```bash
execute(command="python skills/excel-xlsx/scripts/view.py --file output/sales.xlsx")
```

Add `--show-formulas` to confirm formulas (not computed values) were stored.
Add `--max-rows 20` to see more rows.

### Step 3 — Edit an existing workbook (optional)

```bash
execute(command="python skills/excel-xlsx/scripts/edit.py --help")
```

- `--cell C5 --value '=B5*D5'` sets a cell (repeat `--cell`/`--value` for many).
- `--append-rows '[\"Gizmo,3,7.5,=B6*C6\"]'` appends rows to the active sheet.

### Step 4 — Report

Tell the user the file path, sheet names, row/column counts, and any formulas.

## Key Rules (when you must work beyond the scripts)

- **Formulas win**: write `=A1+B1`, never the precomputed number. `openpyxl`
  does not calculate — Excel computes on open.
- **Long IDs/phones as text**: use `--text-cols`, or the digits get truncated.
- **Dates**: store as real dates with a number format, not as strings.
- **Never load with `data_only=True` then save** — it flattens formulas into
  static values. The scripts load read-only with `data_only=True` only for
  inspection; they never re-save in that mode.
- **Merged cells**: only the top-left cell holds the value; the scripts handle
  this, but if you edit manually, write to the top-left.

## Common Traps

- Column off-by-one between A1 notation and 0-based indexes — the scripts use
  A1, so prefer them over hand-written code.
- Mixed text/number columns need explicit typing on both read and write.
- Hidden rows, named ranges, and data validations can carry business logic
  invisible in a quick skim — mention these to the user if they matter.
