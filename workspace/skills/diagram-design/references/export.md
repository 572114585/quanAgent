# Export to PNG / SVG

Convert a generated diagram HTML file into a portable `.svg` and/or `.png` under `output/`. **Manual only — never run unprompted.**

## Trigger

Load this file when the user asks in natural language to export, save, rasterize, convert, or download a diagram as `.svg` or `.png`. Typical phrasings:

- "export this as PNG"
- "save as SVG"
- "give me a PNG of that diagram"
- "rasterize it"
- "convert to png and svg"

There is no slash command in DeepAgent. Natural language is the only trigger.

## Scope

SVG export is **diagram-only** — just the `<svg>` node. Editorial wrappers (header, summary cards, footer in `-full` variants) are dropped.

PNG via `render_html` is a **full-page screenshot** of the HTML (including title/cards). If the user needs diagram-only PNG, say so: DeepAgent `render_html` does not clip to the SVG bounding box. Offer SVG instead, or a full-page PNG as a preview.

If the user explicitly asks for "a screenshot of the whole page including the cards", `render_html` is the right tool.

## SVG export procedure

Run the packaged script (stdlib, no Playwright):

```text
python skills/diagram-design/scripts/export_svg.py --file output/<slug>.html --out output/<slug>.svg
```

The script:

1. Reads the source HTML (must be under `output/`, `tmp/`, `skills/`, or `uploads/`).
2. Extracts the **first** `<svg>...</svg>` block (nested SVGs included).
3. Ensures `xmlns="http://www.w3.org/2000/svg"`.
4. Injects Google Fonts `@import` with XML-escaped `&amp;` into `<defs>`.
5. Prepends `<?xml version="1.0" encoding="UTF-8"?>`.
6. Writes only under `output/` or `tmp/`.

Do not extract SVG by hand with `python -c`. Do not write next to files under `skills/`.

### Caveat to surface to the user

Tools that don't fetch remote fonts at import time (offline Illustrator, some Figma import paths, older SVG viewers) will substitute typography. The SVG renders correctly in any modern browser. For pixel-previews, recommend the PNG path.

## PNG export procedure

Call the DeepAgent **`render_html` tool**. Never `python -c`, never a temp Playwright snippet, never `playwright install` from this skill.

```text
render_html(html_path="output/<slug>.html")
```

Optional: set `width` / `height` to match the size preset (e.g. 1920×1080 for `slide-16x9`, `full_page=false`). Default wait is enough for Google Fonts; increase `wait_ms` if fonts look missing.

If `render_html` reports Playwright is not installed, surface that error to the user and stop. Do not auto-install.

### Output naming

Default PNG path is the HTML path with `.png` (still under `output/`). Honour an explicit `output_path` under `output/` or `tmp/`.

## Sizing the export

SVG pixel size follows the diagram `viewBox`. PNG pixel size follows `render_html` viewport × device pixels.

| Destination | render_html hint |
|---|---|
| Docs, README, wiki | defaults (1440×900, full_page true) |
| Slide deck | `width=1920, height=1080, full_page=false` |
| Inline thumbnail | `width=960, height=540, full_page=false` |

If the target aspect ratio doesn't match the `viewBox`, say so and offer to redraw at the matching preset from [`output-spec.md`](output-spec.md). Padding or cropping a finished diagram to fit a frame is not an export operation.

## Edge cases

- **Source is `assets/index.html`** (gallery, multiple SVGs): refuse and ask which specific diagram file they meant.
- **No `<svg>` block found**: the source isn't a diagram file. Tell the user; don't write anything.
- **Surrounding HTML matters**: `render_html` captures the page; `export_svg.py` does not.
- **Motion HTML**: `render_html` captures whatever is on screen after `wait_ms`. Prefer exporting the static HTML variant.

## What this skill never does

- Modifies the source HTML.
- Adds export buttons or extra `<script>` tags.
- Auto-emits `.svg` or `.png` alongside HTML generation. Manual on every call.
- Runs `python -c`, writes a temp `.py` under `tmp/` to drive Playwright, or starts a local HTTP server.
