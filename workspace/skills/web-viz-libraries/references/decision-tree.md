# Decision Tree — Extended Library Routing

This is the extended version of the decision tree in SKILL.md. Use this when the user's request is ambiguous or when multiple libraries could fit.

---

## Decision Tree by User Intent

### "I want a chart"

```
User says "chart" / "graph" / "图表" / "柱状图" / "折线图" / "饼图"
│
├─ Standard chart type (bar/line/pie/scatter/area)?
│  └─ YES → echarts (renderer:'svg' for PNG/PDF, 'canvas' for interactive)
│
├─ Specialized chart (K-line/heatmap/sankey/funnel/gauge/boxplot/candlestick)?
│  └─ YES → echarts (built-in support)
│
├─ Highly custom visualization (node graph / tree / chord / custom shapes)?
│  └─ YES → echarts (try built-in first) OR D3 (if echarts can't do it)
│
├─ Real-time streaming data?
│  └─ YES → echarts (use `appendData` API or `setOption` with merge)
│
└─ 3D chart (3D bar / 3D scatter / surface)?
   └─ YES → echarts with `gl` extension (echarts-gl) OR Three.js
```

**echarts vs D3 vs Chart.js**:
- **echarts**: Most chart types out of the box, SVG renderer for PDF, ~280KB. **Default choice.**
- **D3 v7**: Maximum freedom, but you write more code. Use when echarts can't do what you need.
- **Chart.js**: Simpler API, fewer chart types, canvas-only (no PDF vector). Use for quick prototypes.

---

### "I want 3D"

```
User says "3D" / "三维" / "立体"
│
├─ "I want to control every detail (lighting / material / geometry / shader)"
│  └─ YES → Three.js
│     ├─ Simple scene (just objects + camera)? → three-basic.html template
│     └─ Need OrbitControls / GLTFLoader / post-processing? → three-importmap.html template
│
├─ "I just want it to look cool, don't want to write 3D code"
│  └─ YES → Spline
│     └─ Find a scene on spline.design community → Remix → Export → copy scene URL
│
├─ "I want shader effects (fluid / fractal / starfield / volumetric)"
│  └─ YES → Shadertoy (copy shader code) OR Three.js with custom ShaderMaterial
│
└─ "I want 3D for a PDF/print document"
   └─ ⚠️ PROBLEM: WebGL doesn't enter PDF print stream
      ├─ Option A: Render as PNG with `render_html` → embed PNG in PDF
      └─ Option B: Use echarts-gl (renders 3D charts with WebGL, screenshot to PNG)
```

---

### "I want animation"

```
User says "animation" / "动画" / "动效"
│
├─ "Physics-based (gravity / collision / bouncing / dragging)"
│  └─ YES → Matter.js (2D physics)
│
├─ "Vector animation with state machine (UI motion / character / icon)"
│  └─ YES → Rive (download .riv from rive.app community)
│
├─ "Pre-made 3D animation (don't want to code)"
│  └─ YES → Spline (Remix from community)
│
├─ "Shader-based animation (flowing colors / plasma / noise)"
│  └─ YES → Shadertoy (copy shader) OR Three.js with custom shader
│
├─ "No-code 2D interactive effect (parallax / particles / displacement)"
│  └─ YES → Unicorn Studio (Remix from community)
│
├─ "Simple UI micro-interaction (hover / press / fade-in)"
│  └─ YES → Pure CSS transitions/animations — no library needed!
│
└─ "Complex orchestrated timeline (multi-scene video-like)"
   └─ YES → Custom `useTime` + easing + interpolate (see web-design-engineer skill)
      └─ Avoid Framer Motion / GSAP / Lottie unless explicitly requested
```

**Important**: For PNG/PDF delivery, animations only capture a single frame. Use interactive HTML delivery for animations to make sense.

---

### "I want a map"

```
User says "map" / "地图" / "地理位置"
│
├─ "Interactive (draggable / zoomable / clickable markers)"
│  └─ YES → Mapbox GL JS (vector tiles, crisp at any zoom)
│     ├─ Has access token? → Use directly
│     └─ No token? → Use placeholder + TODO comment, point user to mapbox.com
│
├─ "Static map image (just for display, no interaction)"
│  └─ YES → Mapbox Static Images API (single PNG, no JS library)
│     OR Leaflet with static tile layer (lighter than Mapbox)
│
├─ "Data overlay on map (choropleth / heatmap / flow map)"
│  └─ YES → Mapbox GL JS with custom GeoJSON layer
│     OR echarts with `geo` component (simpler, no token needed)
│
└─ "3D terrain / buildings on map"
   └─ YES → Mapbox GL JS with `terrain` and `fill-extrusion` layer
```

**Mapbox vs Leaflet vs echarts geo**:
- **Mapbox**: Best visual quality, vector tiles, requires token, 50k free loads/month
- **Leaflet**: Open-source, no token, simpler API, raster tiles (less crisp)
- **echarts geo**: Built-in, no token, good for data visualization on map, less detailed base map

---

## Complexity Tier (for LLM effort estimation)

| Tier | Library | LLM code volume | Risk of failure |
|---|---|---|---|
| **Easy** | echarts, Matter.js | ~30-80 lines | Low — well-documented API |
| **Medium** | Three.js (basic), Mapbox, Spline embed | ~80-200 lines | Medium — importmap / token / scene URL |
| **Hard** | Three.js (importmap + addons), Rive | ~150-300 lines | Medium — module loading, wasm |
| **Very Hard** | Shadertoy (custom shader), Three.js ShaderMaterial | ~200-500 lines | High — shader debugging is hard |
| **External Asset** | Spline, Rive, Unicorn Studio, Mapbox | Varies | Low code, but requires user-provided asset (scene URL / .riv / project ID / token) |

**Implication**: If user request is vague ("make it look cool") and you're considering a Very Hard library, **switch to an External Asset library** (Spline / Unicorn Studio) — let the community do the heavy lifting.

---

## Alternative Libraries (not in the main 8, but worth knowing)

| Library | Use case | Why not in main 8 |
|---|---|---|
| **Chart.js** | Simple charts | echarts is more capable (PDF svg, more chart types) |
| **D3 v7** | Custom visualization | Steeper learning curve, echarts covers 90% of cases |
| **Leaflet** | Lightweight maps | Mapbox has better visual quality, vector tiles |
| **Plotly.js** | Scientific plots | echarts covers most scientific charts, smaller bundle |
| **Anime.js** / **GSAP** | Animations | CSS covers 80% of cases, heavy bundle |
| **Lottie** | After Effects animations | Rive is more modern, smaller files, interactive |
| **Popmotion** | Animations | Used as fallback in web-design-engineer, not primary |
| **Pixi.js** | 2D WebGL | Matter.js + canvas is simpler for physics |

---

## Quick "If User Said X, Use Y" Cheat Sheet

| User phrase | Library |
|---|---|
| "柱状图" / "bar chart" | echarts |
| "折线图" / "line chart" | echarts |
| "饼图" / "pie chart" | echarts |
| "K线图" / "candlestick" | echarts |
| "热力图" / "heatmap" | echarts |
| "桑基图" / "sankey" | echarts |
| "关系图" / "graph" | echarts |
| "3D 立方体" / "3D cube" | Three.js (three-basic) |
| "3D 模型查看" / "view GLTF model" | Three.js (three-importmap + GLTFLoader) |
| "3D 设计" / "3D scene" (don't want to code) | Spline |
| "物理动画" / "physics" | Matter.js |
| "重力" / "gravity" | Matter.js |
| "碰撞" / "collision" | Matter.js |
| "矢量动画" / "vector animation" | Rive |
| "UI 动效" / "UI motion" | Rive OR pure CSS |
| "地图" / "map" | Mapbox |
| "暗色地图" / "dark map" | Mapbox (dark-v11 style) |
| "写实地图" / "satellite map" | Mapbox (satellite-v9 style) |
| "着色器" / "shader" | Shadertoy |
| "流体效果" / "fluid effect" | Shadertoy |
| "粒子效果" / "particle effect" (no-code) | Unicorn Studio |
| "视差效果" / "parallax" (no-code) | Unicorn Studio |
