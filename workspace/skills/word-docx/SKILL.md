---
name: word-docx
description: "Create, inspect, and edit Microsoft Word documents and DOCX files. Use when (1) the task is about Word or `.docx`; (2) the file includes tracked changes, comments, fields, tables, templates, or page layout constraints; (3) the document must survive round-trip editing without formatting drift."
---

## Instructions

When the user asks you to create or edit a Word document, follow these steps:

### Step 1: Choose the right library

- Use `python-docx` for creating and editing `.docx` files.
- Use `openpyxl` or `pandas` if the task is actually about spreadsheets, not documents.

### Step 2: Write a Python script and execute it

Use the `execute` tool to run Python code. Always write a complete, self-contained script.

**Creating a new document:**
```python
execute("python -c \"
from docx import Document
doc = Document()
doc.add_heading('Title', level=1)
doc.add_paragraph('Hello, this is a Word document.')
doc.save('output.docx')
\"")
```

For complex documents, write the script to a file first, then execute it:
```python
execute("cat > /tmp/create_doc.py << 'PYEOF'\nfrom docx import Document\nfrom docx.shared import Inches, Pt\n\ndoc = Document()\ndoc.add_heading('Report', level=1)\np = doc.add_paragraph()\np.add_run('Bold text').bold = True\np.add_run(' and ')\np.add_run('italic text').italic = True\ndoc.save('output.docx')\nPYEOF")
execute("python /tmp/create_doc.py")
```

**Editing an existing document:**
```python
execute("python -c \"
from docx import Document
doc = Document('existing.docx')
doc.add_paragraph('Appended paragraph.')
doc.save('existing.docx')
\"")
```

**Reading/inspecting a document:**
```python
execute("python -c \"
from docx import Document
doc = Document('file.docx')
for i, p in enumerate(doc.paragraphs[:10]):
    print(f'[{i}] style={p.style.name}: {p.text[:80]}')
\"")
```

### Step 3: Save the file to the workspace

Save output files under the current workspace directory. Use a descriptive filename.

### Step 4: Verify the result

After creating or editing, always verify by reading the document back:
```python
execute("python -c \"
from docx import Document
doc = Document('output.docx')
print(f'Paragraphs: {len(doc.paragraphs)}')
print(f'Tables: {len(doc.tables)}')
for p in doc.paragraphs[:5]:
    print(f'  [{p.style.name}] {p.text[:80]}')
\"")
```

### Step 5: Report to the user

Tell the user the file is ready, its location, and a brief summary of its contents.

## Key Rules

- **Styles**: Prefer named styles over direct formatting. Extend existing styles when editing, don't invent new ones.
- **Lists**: Use `doc.add_paragraph('item', style='List Bullet')` for bullets. Numbering is managed by Word's numbering definitions.
- **Tables**: Use `doc.add_table(rows=N, cols=M)` and set column widths explicitly when layout matters.
- **Sections**: Page layout (margins, orientation, headers/footers) lives in sections. Use section breaks for layout changes.
- **Tracked changes**: When editing reviewed documents, make minimal replacements instead of rewriting whole paragraphs.
- **Fields**: TOC, page numbers, and cross-references are fields. Edit field sources carefully; cached values may lag.

## Common Traps

- Copy-paste between documents can import unwanted styles and numbering.
- One visible phrase can be split across multiple runs — don't assume simple text replacement works.
- Empty paragraphs used as spacing make templates fragile; use paragraph spacing settings instead.
- Table auto-fit can look fine in Word but drift in Google Docs or LibreOffice.
- Restarting lists manually usually fails — numbering state lives outside paragraph text.
