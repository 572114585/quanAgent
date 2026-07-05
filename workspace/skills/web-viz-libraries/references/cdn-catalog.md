# CDN Catalog — Pinned Versions & Integrity Hashes

All CDN URLs in this catalog are **pinned to specific tested versions**. Do not use `@latest` or guess from training data. When in doubt, prefer jsdelivr over unpkg (better cache hit rate in China).

---

## 1. Apache ECharts

| Property | Value |
|---|---|
| **Pinned version** | 5.x latest (5.5+ recommended; 6.0 released 2025 may have breaking changes) |
| **Primary CDN** | `https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js` |
| **Fallback CDN** | `https://unpkg.com/echarts@5/dist/echarts.min.js` |
| **Global variable** | `echarts` |
| **UMD / ESM** | UMD (just `<script src>`) |
| **Size (gzipped)** | ~280KB |
| **Official site** | https://echarts.apache.org/ |
| **Notes** | Use `echarts@6` for the latest 6.x line. For PDF delivery, must use `renderer:'svg'` option. |

---

## 2. Three.js

### 2a. UMD build (simple scenes, no addons)

| Property | Value |
|---|---|
| **Pinned version** | 0.160.0 |
| **Primary CDN** | `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js` |
| **Fallback CDN** | `https://unpkg.com/three@0.160.0/build/three.min.js` |
| **Global variable** | `THREE` |
| **UMD / ESM** | UMD |
| **Size (gzipped)** | ~150KB |
| **Notes** | For PNG delivery, MUST set `preserveDrawingBuffer: true` in `WebGLRenderer` options or screenshot will be black. |

### 2b. ES Module build (with addons like OrbitControls, GLTFLoader)

| Property | Value |
|---|---|
| **Pinned version** | 0.160.0 |
| **Module CDN** | `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js` |
| **Addons base** | `https://cdn.jsdelivr.net/npm/three@0.160.0/examples/jsm/` |
| **Usage** | Requires `<script type="importmap">` — see `embed-templates/three-importmap.html` |
| **Notes** | Addons (OrbitControls, GLTFLoader, STLLoader, etc.) are NOT separate npm packages — they live under `examples/jsm/`. |

---

## 3. Matter.js

| Property | Value |
|---|---|
| **Pinned version** | 0.20.0 |
| **Primary CDN** | `https://cdn.jsdelivr.net/npm/matter-js@0.20.0/build/matter.min.js` |
| **Fallback CDN** | `https://cdn.bootcdn.net/ajax/libs/matter-js/0.20.0/matter.js` |
| **Global variable** | `Matter` |
| **UMD / ESM** | UMD |
| **Size (gzipped)** | ~75KB |
| **Official site** | https://brm.io/matter-js/ |
| **Notes** | Lightweight 2D physics engine. Built-in `Render` uses canvas. For mouse interaction, use `MouseConstraint`. |

---

## 4. Mapbox GL JS

| Property | Value |
|---|---|
| **Pinned version** | 3.2.0 |
| **JS CDN** | `https://api.mapbox.com/mapbox-gl-js/v3.2.0/mapbox-gl.js` |
| **CSS CDN** | `https://api.mapbox.com/mapbox-gl-js/v3.2.0/mapbox-gl.css` |
| **Global variable** | `mapboxgl` |
| **UMD / ESM** | UMD |
| **Size (gzipped)** | ~200KB |
| **Official site** | https://docs.mapbox.com/mapbox-gl-js/ |
| **Access token** | **Required** — free tier: 50k loads/month. Get from https://account.mapbox.com/access-tokens/ |
| **Preset styles** | `mapbox://styles/mapbox/streets-v12` (standard), `dark-v11` (dark), `light-v10` (light), `satellite-v9` (satellite), `satellite-streets-v12` (hybrid) |
| **Notes** | Vector tiles — crisp at any zoom. Online only (no offline). WebGL-based, does NOT enter PDF print stream. |

---

## 5. Spline (spline-viewer Web Component)

| Property | Value |
|---|---|
| **Pinned version** | 1.9.82 |
| **Primary CDN** | `https://unpkg.com/@splinetool/viewer@1.9.82/build/spline-viewer.js` |
| **Usage** | `<script type="module" src="...">` + `<spline-viewer url="YOUR_SCENE_URL">` |
| **Scene URL** | Get from spline.design → open project → Export → Copy Embed URL |
| **Size (gzipped)** | ~500KB+ (loads scene + runtime) |
| **Official site** | https://spline.design/ |
| **Notes** | Free version has Spline watermark in bottom-right. Online only. WebGL-based. |

### Alternative: iframe embed (simpler, less control)

If you don't need to control the scene via JS, iframe embed is simpler — get the iframe URL from Spline's Export dialog and paste directly.

---

## 6. Rive (@rive-app/canvas)

| Property | Value |
|---|---|
| **Pinned version** | 2.17.3 |
| **Primary CDN** | `https://unpkg.com/@rive-app/canvas@2.17.3` |
| **Global variable** | `RiveCanvas` |
| **UMD / ESM** | UMD with wasm |
| **Size (gzipped)** | ~150KB JS + ~200KB wasm |
| **Official site** | https://rive.app/ |
| **Asset file** | `.riv` file — get from rive.app community (https://rive.app/community) or make your own in editor.rive.app |
| **Notes** | First load is slow (wasm compile). Use `wait_ms=3000+` for screenshot. Vector-based, scales crisply. |

### Loading variants

- `@rive-app/canvas` — canvas renderer (default, faster)
- `@rive-app/canvas-advanced` — low-level API for state machine control
- `@rive-app/webgl` — WebGL renderer (slower but more effects)

---

## 7. Shadertoy (custom WebGL boilerplate)

| Property | Value |
|---|---|
| **CDN** | **None** — Shadertoy doesn't provide a runtime CDN |
| **Approach** | Copy shader code from https://www.shadertoy.com/browse, adapt into your own WebGL boilerplate |
| **Boilerplate** | See `embed-templates/shadertoy-boilerplate.html` for a minimal WebGL2 canvas + shader wrapper |
| **Uniforms to adapt** | `iTime` (seconds since start), `iResolution` (canvas size in pixels), `iMouse` (mouse position) |
| **Notes** | Multi-tab shaders: each tab is a separate shader pass — you need multiple framebuffers and ping-pong rendering. Start with single-tab shaders. |

---

## 8. Unicorn Studio

| Property | Value |
|---|---|
| **Embed script** | `https://cdn.unicorn.studio/embed.js` (URL from Export dialog may differ) |
| **Usage** | `<script src="...embed.js"></script>` + `<div data-us-project="YOUR_PROJECT_ID"></div>` |
| **Project ID** | Get from unicorn.studio → open project → Export → Embed → HTML |
| **Size (gzipped)** | ~200KB+ runtime |
| **Official site** | https://unicorn.studio/ |
| **Notes** | No-code WebGL interactive effects tool. Free version has watermark. Online only. |

---

## General Notes

### CDN Choice: jsdelivr vs unpkg

- **jsdelivr** (`https://cdn.jsdelivr.net/npm/...`): Better cache hit rate in mainland China, recommended default
- **unpkg** (`https://unpkg.com/...`): More reliable in some regions, fallback option
- Both serve the same npm packages — interchangeable

### Integrity Hashes

For production use, add `integrity` attribute with SRI hash:

```html
<script src="https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js"
        integrity="sha384-<hash>"
        crossorigin="anonymous"></script>
```

Get hash from https://www.srihash.org/ by pasting the CDN URL. For LLM-generated HTML artifacts (not production), integrity is optional — prioritize working code over SRI verification.

### Version Pinning Strategy

- **Pin to specific version** (e.g., `@5.4.3`): Reproducible, no surprise breakage
- **Pin to major version** (e.g., `@5`): Auto-get latest 5.x, minor version bumps usually safe
- **Never use `@latest`**: May pull breaking changes; LLM training data is also stale

This catalog uses **major-version pinning** for stable libraries (echarts@5, three@0.160) and **specific pinning** for libraries with frequent breaking changes (mapbox-gl@3.2.0, spline-viewer@1.9.82).
