---
name: excel-xlsx
description: "Create, inspect, and edit Microsoft Excel workbooks and XLSX files. Use when (1) the task is about Excel, `.xlsx`, `.xlsm`, `.xls`, `.csv`, or `.tsv`; (2) formulas, formatting, workbook structure, or compatibility matter; (3) the file must stay reliable after edits."
---

## Instructions

When the user asks you to create or edit an Excel file, follow these steps:

### Step 1: Choose the right library

- Use `openpyxl` when you need formulas, styles, merged cells, multiple sheets, or workbook preservation.
- Use `pandas` for data analysis, reshaping, and CSV-like tasks.
- When in doubt, use `openpyxl` — it gives you full control over the workbook.

### Step 2: Write a Python script and execute it

Use the `execute` tool to run Python code. Always write a complete, self-contained script.

**Creating a new workbook:**
```python
execute("python -c \"
import openpyxl
wb = openpyxl.Workbook()
ws = wb.active
ws.title = 'Sheet1'
ws['A1'] = 'Hello'
ws['B1'] = 42
wb.save('output.xlsx')
\"")
```

For complex workbooks, write the script to a file first, then execute it:
```python
execute("cat > /tmp/create_xl.py << 'PYEOF'\nimport openpyxl\nwb = openpyxl.Workbook()\nws = wb.active\nws['A1'] = 'Name'\nws['B1'] = 'Score'\nwb.save('output.xlsx')\nPYEOF")
execute("python /tmp/create_xl.py")
```

**Editing an existing workbook:**
```python
execute("python -c \"
import openpyxl
wb = openpyxl.load_workbook('existing.xlsx')
ws = wb.active
ws['C1'] = 'New Column'
wb.save('existing.xlsx')
\"")
```

**Reading/inspecting a workbook:**
```python
execute("python -c \"
import openpyxl
wb = openpyxl.load_workbook('file.xlsx', data_only=True)
ws = wb.active
for row in ws.iter_rows(max_row=5, values_only=True):
    print(row)
\"")
```

### Step 3: Save the file to the workspace

Save output files under the current workspace directory so the user can access them. Use a descriptive filename.

### Step 4: Verify the result

After creating or editing, always verify by reading the file back:
```python
execute("python -c \"
import openpyxl
wb = openpyxl.load_workbook('output.xlsx', data_only=True)
ws = wb.active
print(f'Sheets: {wb.sheetnames}')
print(f'Rows: {ws.max_row}, Cols: {ws.max_column}')
for row in ws.iter_rows(max_row=min(5, ws.max_row), values_only=True):
    print(row)
\"")
```

### Step 5: Report to the user

Tell the user the file is ready, its location, and a brief summary of its contents.

## Key Rules

- **Formulas**: Write formulas into cells (e.g., `ws['C1'] = '=A1+B1'`) instead of hardcoding computed values.
- **Dates**: Excel stores dates as serial numbers. Use `openpyxl` datetime utilities or set explicit number formats.
- **Data types**: Store long IDs, phone numbers, and ZIP codes as text (`ws['A1'] = '00123'`) to prevent truncation.
- **Styles**: Match existing styles when editing. Use named styles over direct formatting.
- **Merged cells**: Only the top-left cell of a merged range stores the value.
- **Recalculation**: `openpyxl` preserves formulas but does not calculate them. The user will see results when they open the file in Excel.

## Common Traps

- Column indexing varies across tools — off-by-one mistakes are common in formulas.
- Opening a workbook with `data_only=True` and then saving will flatten formulas into static values.
- Mixed text-number columns need explicit handling on read and write.
- Hidden rows, named ranges, and validations can carry business logic invisible in a quick skim.
