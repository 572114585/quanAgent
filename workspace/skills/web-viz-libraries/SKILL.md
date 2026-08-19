---
name: web-viz-libraries
description: "Quick reference for embedding 8 visualization libraries (echarts, Three.js, Matter.js, Mapbox, Spline, Rive, Shadertoy, Unicorn Studio) into HTML artifacts. Use when the user wants charts, 3D, physics, maps, animations, or shader effects in a web page. Provides pinned CDN URLs, minimal embed templates, and a decision tree. Not a design system — for visual design language use web-design-engineer."
allowed-tools: read_file write_file edit_file web_search render_html
---

# Web Visualization Libraries — Quick Reference

This skill is a **CDN + embed-template lookup** for 8 commonly-used frontend visualization libraries. It does NOT design pages — it tells you which library fits the user's need, which CDN URL to pin, and gives you a minimal HTML template to copy and modify.

**Core philosophy**: Don't guess CDN versions from training data. Don't write 3D shaders from scratch when the user just wants a chart. Pick the right library from the decision tree, copy the template, change the data.

---

## Scope

✅ **Applicable**: User wants a web page to contain a chart / 3D scene / physics animation / map / shader effect / vector animation, and you need to know which library to use and how to embed it.

❌ **Not applicable**:
- Visual design language (color / typography / spacing) → use `web-design-engineer`
- **Editorial architecture / flowchart / sequence / state / ER / org chart / swimlane / timeline diagrams as standalone HTML/SVG** → use `diagram-design` (editorial SVG design system, not a JS chart library)
- Pure static document → PDF conversion → use `md-to-pdf`
- Backend data processing, no visual output
- **User provided an object reference image and wants a procedural / animation-ready Three.js reconstruction** → use `object-sculptor` (not this skill)

---

## Step 1: Pick the Library (Decision Tree)

| User asks for | Use | Why |
|---|---|---|
| Editorial architecture / flowchart / sequence / state machine / ER / org chart (standalone HTML/SVG, not a JS chart) | **`diagram-design` skill** | Opinionated SVG design system; stop using this skill |
| Bar / line / pie / scatter / heatmap / K-line / sankey / funnel / gauge chart | **echarts** | One-line CDN, `renderer:'svg'` makes PNG and PDF both crisp |
| Complex custom visualization (node graph / tree / chord) | **echarts** or **D3** | echarts has more built-in types, D3 is more freeform |
| Object reference image → procedural / code-only Three.js model | **`object-sculptor` skill** | Spec + geometry factory + visual gates; stop using this skill |
| 3D scene / object / lighting / material (no reference reconstruction) | **Three.js** | Full WebGL engine, code is controllable |
| Ready-made 3D design (user doesn't want to write 3D code) | **Spline** | Remix from community + embed `<spline-viewer>` Web Component |
| 2D physics animation (gravity / collision / constraint) | **Matter.js** | One-line CDN, intuitive API, mouse-interactive |
| 2D vector animation / UI motion (state machine) | **Rive** | Community `.riv` file + wasm runtime |
| Map (draggable / zoomable / dark / satellite) | **Mapbox** | Vector tiles, requires free token |
| WebGL shader effect (fluid / terrain / fractal / starfield) | **Shadertoy** | Copy community shader code + adapt uniforms |
| 2D no-code interactive effect (parallax / particles) | **Unicorn Studio** | Editor Remix + Embed HTML |

> Extended routing table (with screenshots, complexity tier, alternative libraries) → `references/decision-tree.md`

---

## Step 2: Check the Delivery Scenario Compatibility

Different libraries work differently across the three delivery channels. **Pick the library with the delivery channel in mind**:

| Library | PNG screenshot (`render_html`) | PDF (`render_pdf.py`) | Interactive HTML (browser) | Recommended `wait_ms` |
|---|---|---|---|---|
| echarts (svg renderer) | ★★★★★ crisp | ★★★★ vector | ✅ | 1500 |
| echarts (canvas renderer) | ★★★★ | ★★ rasterized | ✅ | 1500 |
| Three.js | ★★★★ needs `preserveDrawingBuffer:true` | ✗ WebGL doesn't enter print stream | ✅ | 2500 |
| Matter.js | ★★ static frame only | ✗ | ✅ | 2000 |
| Mapbox | ★★★★ vector tiles | ✗ | ✅ | 2500 |
| Spline | ★★★ WebGL | ✗ | ✅ | 3000 |
| Rive | ★★ static frame | ✗ | ✅ | 3000 (wasm slow) |
| Shadertoy | ★★★ | ✗ | ✅ | 2000 |
| Unicorn Studio | ★★★ | ✗ | ✅ | 2500 |

**Key takeaway**:
- For **PDF delivery**, only echarts (svg renderer) works well. WebGL libraries (Three.js / Spline / Rive / Shadertoy / Unicorn / Mapbox) do NOT enter the print stream.
- For **PNG screenshot**, all libraries work, but Matter.js / Rive (animations) only capture a single frame — make sure the frame is meaningful.
- For **interactive HTML**, all 8 libraries work — deliver the `.html` file directly.

---

## Step 3: Get the CDN URL and Template

### CDN Quick Reference (pinned versions)

| Library | CDN URL | Global var |
|---|---|---|
| echarts 5 | `https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js` | `echarts` |
| three.js 0.160 (UMD) | `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js` | `THREE` |
| three.js 0.160 (ESM) | `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js` + importmap | `import * as THREE` |
| matter-js 0.20 | `https://cdn.jsdelivr.net/npm/matter-js@0.20.0/build/matter.min.js` | `Matter` |
| mapbox-gl 3.2 (JS) | `https://api.mapbox.com/mapbox-gl-js/v3.2.0/mapbox-gl.js` | `mapboxgl` |
| mapbox-gl 3.2 (CSS) | `https://api.mapbox.com/mapbox-gl-js/v3.2.0/mapbox-gl.css` | — |
| spline-viewer 1.9 | `https://unpkg.com/@splinetool/viewer@1.9.82/build/spline-viewer.js` (`type="module"`) | `<spline-viewer>` |
| rive canvas 2.17 | `https://unpkg.com/@rive-app/canvas@2.17.3` | `RiveCanvas` |
| Shadertoy | No official CDN — write WebGL boilerplate yourself (see template) | — |
| Unicorn Studio | `https://cdn.unicorn.studio/embed.js` (URL from Export dialog) | — |

> Full catalog with integrity hashes, version notes, fallback CDNs → `references/cdn-catalog.md`

### Embed Templates

Each template is a complete `<!DOCTYPE html>` document that opens directly in a browser. Copy → modify the data / config → `write_file output/x.html`.

| Template | What it does |
|---|---|
| `references/embed-templates/echarts.html` | Bar chart with `renderer:'svg'` (PNG/PDF friendly) |
| `references/embed-templates/three-basic.html` | UMD global `THREE`, rotating cube with `preserveDrawingBuffer:true` |
| `references/embed-templates/three-importmap.html` | ES Module + importmap, `OrbitControls` for interactive 3D |
| `references/embed-templates/matter-physics.html` | Engine + Render + Runner + MouseConstraint, falling balls |
| `references/embed-templates/mapbox-dark.html` | Dark style map, `accessToken` placeholder for user to fill |
| `references/embed-templates/spline-web-component.html` | `<spline-viewer>` element, scene URL placeholder |
| `references/embed-templates/rive-canvas.html` | `<canvas>` + `RiveCanvas.Rive()`, `.riv` path placeholder |
| `references/embed-templates/shadertoy-boilerplate.html` | WebGL2 canvas + shader boilerplate, paste `mainImage` body |
| `references/embed-templates/unicorn-embed.html` | Unicorn Studio embed code, project ID placeholder |

---

## Step 4: Token / Account Requirements

Some libraries require the user to register or prepare assets in advance. **You cannot do this for them** — leave a placeholder and tell the user to fill it in.

| Library | Requirement | How to handle |
|---|---|---|
| **Mapbox** | Free access token from mapbox.com | Write `mapboxgl.accessToken = 'YOUR_MAPBOX_TOKEN'` in HTML, comment `// TODO: replace with your token from https://account.mapbox.com/access-tokens/` |
| **Spline** | Remix a scene on spline.design, copy scene URL | Write `<spline-viewer url="YOUR_SCENE_URL">`, comment `<!-- TODO: replace with your scene URL from spline.design Export -->` |
| **Rive** | Download a `.riv` file from rive.app community or make your own | Write `src: 'YOUR_RIV_FILE.riv'`, comment `// TODO: replace with your .riv file path` |
| **Unicorn Studio** | Remix on unicorn.studio, copy project ID from Export | Write `data-us-project="YOUR_PROJECT_ID"`, comment `<!-- TODO: replace with your project ID from unicorn.studio Export -->` |

---

## Step 5: Workflow (End-to-End)

1. User says: "画个柱状图" / "加个 3D 立方体" / "做物理动画" / "加地图"
2. Read the **Decision Tree** above → pick the library
3. Check the **Delivery Scenario Compatibility** table → confirm the library fits the user's delivery target (PNG / PDF / interactive HTML)
4. `read_file` the corresponding `references/embed-templates/<lib>.html` template
5. Modify the data / config in the template → `write_file output/<name>.html`
6. If a token / asset is required and user hasn't provided it → leave placeholder + tell user
7. Render & deliver by delivery channel:
   - **PNG**: `render_html(html_path="output/<name>.html", wait_ms=<推荐值>)`
   - **PDF**: `python skills/md-to-pdf/scripts/render_pdf.py --html output/<name>.html --out output/<name>.pdf --wait-ms <推荐值>`
   - **Interactive HTML**: deliver the `.html` file directly, user opens in browser

---

## Step 6: Verification Checklist

Before delivering the artifact:

- [ ] Browser console shows no errors when opening the HTML
- [ ] CDN URL is the pinned version from the table above (not a guessed version)
- [ ] `wait_ms` matches the recommended value for the library (heavy libs need 2000-3000)
- [ ] For WebGL libraries (Three.js / Spline / Rive / Shadertoy / Unicorn / Mapbox) delivered as PNG: viewport size is set to capture the canvas fully
- [ ] For PDF delivery: only echarts (svg renderer) is used — WebGL libraries don't enter print stream
- [ ] Token / asset placeholders are clearly marked with `TODO` comments if user hasn't provided them
- [ ] For screenshot delivery: `render_html` is called to produce a PNG alongside the HTML

---

## References Routing

**Path convention**: all `references/...` paths are relative to this skill's directory. When calling `read_file`, prefix with the full skill path: `skills/web-viz-libraries/references/...`.

| Need | Read |
|---|---|
| Full CDN list with integrity hashes, version notes, fallback CDNs | `references/cdn-catalog.md` |
| Extended decision tree with screenshots, complexity tier, alternatives | `references/decision-tree.md` |
| Single library's minimal HTML template | `references/embed-templates/<lib>.html` |

---

## Anti-Patterns

- ❌ Guessing CDN versions from training data (e.g., `echarts@4.8.0` — outdated, may have bugs)
- ❌ Writing Three.js shader code from scratch when user just wants "a 3D effect" — point them to Spline community instead
- ❌ Writing Shadertoy shader from scratch — copy from shadertoy.com/browse and adapt
- ❌ Using `renderer:'canvas'` for echarts when delivering to PDF — use `renderer:'svg'` for vector output
- ❌ Forgetting `preserveDrawingBuffer:true` in Three.js when delivering PNG — screenshot will be black
- ❌ Hardcoding a Mapbox token in the HTML — always use placeholder + TODO comment
- ❌ Delivering a WebGL library as PDF — only echarts (svg) works for PDF
- ❌ Setting `wait_ms=1500` (default) for Rive/Spline — wasm load is slow, use 3000+
