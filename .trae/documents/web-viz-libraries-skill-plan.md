# 计划:web-viz-libraries skill + render_pdf wait_ms 可配置化

## 摘要

实施"方案 A + 方案 C"组合,让本项目的 LLM 能像 Claude Code 那样调用 8 个前端可视化库(echarts / Three.js / Matter.js / Mapbox / Spline / Rive / Shadertoy / Unicorn Studio)制作精美网页。

- **方案 C(基础设施)**:把 [render_pdf.py:69](file:///d:/project/workspace/skills/md-to-pdf/scripts/render_pdf.py) 的 hardcode `wait_for_timeout(1000)` 改为可配置 `--wait-ms` 参数,与 [render_html.py](file:///d:/project/tools/render_html.py) 的 `wait_ms` 参数对齐,解锁重型 JS 库的 PDF 渲染。
- **方案 A(能力扩展)**:新建 `workspace/skills/web-viz-libraries/` skill,提供 8 库的 CDN 速查表 + 9 个最小嵌入模板 + 决策树。LLM 写 HTML 时按需查阅,通过 `write_file output/x.html` + `render_html` 或 `render_pdf` 完成交付。

**不改造** `render_html` / `render_pdf` 的渲染逻辑本身——它们已是 Playwright Chromium,原生支持任何前端库。

---

## 当前状态分析(基于 Phase 1 探索)

### 1. render_pdf.py 的瓶颈

[render_pdf.py](file:///d:/project/workspace/skills/md-to-pdf/scripts/render_pdf.py) 当前:

- L67:`await page.goto(html_uri, wait_until="networkidle", timeout=timeout_ms)` — 已等网络空闲
- **L69:`await page.wait_for_timeout(1000)` — hardcode 1000ms**,注释写"等字体/Chart.js/延迟渲染完成"
- L185-186:argparse 有 `--timeout`(页面加载超时,默认 30s),**没有** `--wait-ms`
- `render_html.py` 同类参数叫 `wait_ms`(默认 1500ms),两者命名不一致

**问题**:echarts 复杂图表、Three.js 场景、Rive wasm、Mapbox 瓦片加载普遍需 2000-3000ms,1000ms 不够,导致 PDF 渲染不完整。

### 2. 现有 skill 的 CDN 资源表局限

[web-design-engineer/SKILL.md L434-449](file:///d:/project/workspace/skills/web-design-engineer/SKILL.md) 的 "Common CDN Resources" 表只列了 Chart.js / D3 / Google Fonts。LLM 不知道还有 echarts/three/mapbox 等可用,只能凭训练数据猜 CDN 版本,易出错。

### 3. md-to-pdf skill 的自由设计模式

[md-to-pdf/SKILL.md](file:///d:/project/workspace/skills/md-to-pdf/SKILL.md) 已删除早期"套死模板"模式,改为 LLM 直接 `write_file output/custom.html`。三套 showcase(lite/medium/paper)的 `<head>` 当前无 `<script>`,但结构上 `</style>` 后、`</head>` 前是天然挂载点,加 CDN 无任何障碍。

### 4. 项目无任何可视化库依赖

[requirement.txt](file:///d:/project/requirement.txt) 只有 Python 侧 playwright/Pillow/pypdf 等;[agent-frontend/package.json](file:///d:/project/agent-frontend/package.json) 是 Tauri+Vue 应用,与渲染管道无关。前端库走 CDN 即可,无需安装。

### 5. 现有 skill 结构参考

[web-design-engineer](file:///d:/project/workspace/skills/web-design-engineer/SKILL.md) 的 front-matter 格式:`name` / `description` / `allowed-tools`。新 skill 沿用此格式。

---

## 提议的改动

### 改动 1:render_pdf.py 的 wait_ms 可配置化(方案 C)

**文件**:[workspace/skills/md-to-pdf/scripts/render_pdf.py](file:///d:/project/workspace/skills/md-to-pdf/scripts/render_pdf.py)

**Why**:解锁重型 JS 库(echarts 复杂图/Three.js/Rive/Mapbox 瓦片)的 PDF 渲染,与 `render_html.py` 的 `wait_ms` 参数对齐。

**What**:
1. 在 `render_html_to_pdf()` 函数签名(L44)新增 `wait_ms: int` 参数
2. 把 L69 的 `await page.wait_for_timeout(1000)` 改为 `await page.wait_for_timeout(wait_ms)`
3. 在 `main_async()`(L134)把 `args.wait_ms` 透传给 `render_html_to_pdf()`
4. 在 `main()` 的 argparse(L176-189)新增 `--wait-ms` 参数,默认 1000(保持向后兼容)
5. 更新顶部 docstring(L3-18)的用法示例,追加 `--wait-ms 3000` 用法

**How(具体代码)**:

```python
# L44 函数签名:新增 wait_ms 参数
async def render_html_to_pdf(html_path: Path, pdf_path: Path,
                              page_size: str, timeout_ms: int,
                              wait_ms: int = 1000) -> dict:
    """用 Playwright 把 HTML 渲染为 PDF。

    关键参数(已验证):
      - wait_until='networkidle'  等网络图片加载完
      - wait_for_timeout(wait_ms) 等字体/图表/JS 库渲染(默认 1000ms,
        重型库如 echarts/Three.js/Rive/Mapbox 建议 2000-3000ms)
      - print_background=True     保留背景色
      - prefer_css_page_size=True 优先用 CSS @page size(让模板的 @page 生效)
    """
    ...

    # L69 改为
    await page.wait_for_timeout(wait_ms)
```

```python
# L153 main_async 透传
    result = await render_html_to_pdf(
        html_path=html_path,
        pdf_path=pdf_path,
        page_size=args.page_size,
        timeout_ms=args.timeout * 1000,
        wait_ms=args.wait_ms,
    )
```

```python
# L185 argparse 新增
    parser.add_argument("--wait-ms", type=int, default=1000,
                        help="页面加载后额外等待毫秒(默认 1000,"
                             "重型 JS 库如 echarts/Three.js/Rive 建议 2000-3000)")
```

```python
# L7-11 docstring 用法示例追加
    # 渲染含重型 JS 库(echarts/Three.js)的 PDF
    python skills/md-to-pdf/scripts/render_pdf.py \
        --html output/report.html \
        --out output/report.pdf \
        --page-size A4 \
        --wait-ms 3000
```

**风险**:无。默认 1000 保持向后兼容,所有现有调用不受影响。

---

### 改动 2:新建 web-viz-libraries skill(方案 A)

**根目录**:`workspace/skills/web-viz-libraries/`

**Why**:让 LLM 在写 HTML 时有 8 个可视化库的"速查手册",知道何时用哪个库、CDN 怎么挂、嵌入模板长什么样。当前 [web-design-engineer](file:///d:/project/workspace/skills/web-design-engineer/SKILL.md) 的 CDN 表只覆盖 Chart.js/D3,不够。

**目录结构**:

```
workspace/skills/web-viz-libraries/
├── SKILL.md                              # 入口:何时触发、决策树、CDN 速查
└── references/
    ├── cdn-catalog.md                    # 8 库的 pinned CDN + integrity hash + 版本
    ├── decision-tree.md                  # "我要做 X → 用 Y 库"路由表
    └── embed-templates/
        ├── echarts.html                  # ECharts 最小模板(svg 渲染器)
        ├── three-basic.html              # Three.js UMD 全局模式(简单场景)
        ├── three-importmap.html          # Three.js ES Module + importmap(用 OrbitControls 等)
        ├── matter-physics.html           # Matter.js 2D 物理引擎
        ├── mapbox-dark.html              # Mapbox GL JS 暗色地图(需 token 占位)
        ├── spline-web-component.html     # Spline <spline-viewer> Web Component
        ├── rive-canvas.html              # Rive @rive-app/canvas 加载 .riv
        ├── shadertoy-boilerplate.html    # Shadertoy 自写 WebGL boilerplate
        └── unicorn-embed.html            # Unicorn Studio embed 代码片段
```

#### SKILL.md 内容大纲

**Front-matter**:
```yaml
---
name: web-viz-libraries
description: "Quick reference for embedding 8 visualization libraries (echarts, Three.js, Matter.js, Mapbox, Spline, Rive, Shadertoy, Unicorn Studio) into HTML artifacts. Use when the user wants charts, 3D, physics, maps, animations, or shader effects in a web page. Provides pinned CDN URLs, minimal embed templates, and a decision tree. Not a design system — for visual design language use web-design-engineer."
allowed-tools: read_file write_file edit_file web_search render_html
---
```

**主体内容**:

1. **Scope**:
   - ✅ 适用:用户要在网页里加图表/3D/物理/地图/动画/特效,需要知道用哪个库、怎么挂 CDN
   - ❌ 不适用:设计语言/排版/配色(用 web-design-engineer);纯静态文档转 PDF(用 md-to-pdf)

2. **Decision Tree(核心,快速路由)**:

| 用户需求 | 推荐库 | 原因 |
|---|---|---|
| 柱状/折线/饼/散点/热力/K线/桑基等图表 | **echarts** | 一行 CDN,svg 模式 PNG/PDF 都清晰 |
| 复杂自定义可视化(节点图/树图/和弦图) | **echarts** 或 D3 | echarts 内置更多图表类型,D3 更自由 |
| 3D 场景/物体/光照/材质 | **Three.js** | 完整 WebGL 引擎,代码可控 |
| 现成 3D 设计(不想自己写) | **Spline** | 社区 Remix + Web Component 嵌入 |
| 2D 物理动画(重力/碰撞/约束) | **Matter.js** | CDN 一行,API 直观 |
| 2D 矢量动画/UI 动效(状态机) | **Rive** | 社区下载 .riv + wasm runtime |
| 地图(可拖拽缩放/暗色/写实) | **Mapbox** | 矢量瓦片,需免费 token |
| WebGL 特效/着色器(流体/地形/分形) | **Shadertoy** | 复制社区代码 + 魔改 |
| 二维 No-code 互动特效(视差/粒子) | **Unicorn Studio** | 编辑器 Remix + Embed |

3. **适用场景三档表**(PNG/PDF/交互):

| 库 | PNG 截图 | PDF | 交互 HTML | 推荐 wait_ms |
|---|---|---|---|---|
| echarts(svg) | ★★★★★ | ★★★★矢量 | ✅ | 1500 |
| echarts(canvas) | ★★★★ | ★★栅格 | ✅ | 1500 |
| Three.js | ★★★★ | ✗ WebGL 不进打印流 | ✅ | 2500 |
| Matter.js | ★★只能定格 | ✗ | ✅ | 2000 |
| Mapbox | ★★★★矢量瓦片 | ✗ | ✅ | 2500 |
| Spline | ★★★ WebGL | ✗ | ✅ | 3000 |
| Rive | ★★定格 | ✗ | ✅ | 3000(wasm 慢) |
| Shadertoy | ★★★ | ✗ | ✅ | 2000 |
| Unicorn Studio | ★★★ | ✗ | ✅ | 2500 |

4. **CDN 速查表**(简版,完整版在 references/cdn-catalog.md):

| 库 | CDN( pinned 版本) | 全局变量 |
|---|---|---|
| echarts 5 | `https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js` | `echarts` |
| three.js 0.160 | `https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js` | `THREE` |
| matter-js 0.20 | `https://cdn.jsdelivr.net/npm/matter-js@0.20.0/build/matter.min.js` | `Matter` |
| mapbox-gl 3.2 | `https://api.mapbox.com/mapbox-gl-js/v3.2.0/mapbox-gl.js` + CSS | `mapboxgl` |
| spline-viewer 1.9 | `https://unpkg.com/@splinetool/viewer@1.9.82/build/spline-viewer.js`(`type="module"`) | `<spline-viewer>` |
| rive canvas 2.17 | `https://unpkg.com/@rive-app/canvas@2.17.3` | `RiveCanvas` |
| Shadertoy | 无官方 CDN,自写 WebGL boilerplate(见模板) | - |
| Unicorn Studio | `https://cdn.unicorn.studio/embed.js`(具体 URL 按 Export 给的) | - |

5. **Token / 账号提醒**:
   - **Mapbox** 必须免费注册 token(LLM 无法替用户注册,HTML 里写 `'YOUR_MAPBOX_TOKEN'` 占位让用户替换)
   - **Spline** 免费版有水印,需先在 spline.design Remix 拿 scene URL
   - **Rive** 需先在 rive.app 制作或社区下载 .riv 文件
   - **Unicorn Studio** 需在 unicorn.studio Remix 拿 project ID

6. **工作流程**:
   - Step 1:用户说"画柱状图"/"加 3D 立方体"/"做物理动画" → 读决策树路由到库
   - Step 2:`read_file` 对应的 `references/embed-templates/<lib>.html` 拿模板
   - Step 3:按需修改模板里的数据/配置,`write_file output/x.html`
   - Step 4:按交付场景调用:
     - PNG:`render_html(html_path="output/x.html", wait_ms=<推荐值>)`
     - PDF:`python skills/md-to-pdf/scripts/render_pdf.py --html output/x.html --out output/x.pdf --wait-ms <推荐值>`
     - 交互 HTML:直接交付 .html 文件,用户浏览器打开

7. **References Routing**(沿用 web-design-engineer 模式):
   - 完整 CDN + 版本 + integrity hash → `references/cdn-catalog.md`
   - "我要做 X → 用 Y"路由详表 → `references/decision-tree.md`
   - 单库最小模板 → `references/embed-templates/<lib>.html`

#### 9 个 embed-template 文件内容要点

每个模板都是完整 `<!DOCTYPE html>` 文档,含 `<!DOCTYPE>`/`<head>`/`<body>`/`<script>`,浏览器直接打开可见效果。LLM 复制后改数据即可。

1. **echarts.html**:柱状图示例,`renderer:'svg'`(PNG/PDF 友好),含 `setOption({...})` 占位
2. **three-basic.html**:UMD 全局 `THREE`,旋转立方体 + `preserveDrawingBuffer:true`(截图必需)
3. **three-importmap.html**:ES Module + importmap,引入 `OrbitControls`,带注释说明子模块路径
4. **matter-physics.html**:Engine + Render + Runner + MouseConstraint,地面 + 几个落球,可鼠标拖拽
5. **mapbox-dark.html**:`style:'mapbox://styles/mapbox/dark-v11'`,`accessToken:'YOUR_MAPBOX_TOKEN'` 占位,center 设北京
6. **spline-web-component.html**:`<script type="module" src="...spline-viewer.js">` + `<spline-viewer url="...">`,注释说明需替换 scene URL
7. **rive-canvas.html**:`<canvas>` + `new RiveCanvas.Rive({src:'xxx.riv', canvas:..., autoplay:true})`,注释说明需替换 .riv 路径
8. **shadertoy-boilerplate.html**:WebGL2 canvas + vertex/fragment shader boilerplate,`mainImage(out, in)` 函数体留占位,注释说明从 shadertoy.com 复制代码粘贴位置
9. **unicorn-embed.html**:`<script src="https://cdn.unicorn.studio/embed.js"></script>` + `<div data-us-project="...">`,注释说明需替换 project ID

---

### 改动 3(可选,轻量):web-design-engineer CDN 表追加 8 库

**文件**:[workspace/skills/web-design-engineer/SKILL.md L434-449](file:///d:/project/workspace/skills/web-design-engineer/SKILL.md)

**Why**:让 web-design-engineer 在做"含图表/3D/地图的网页"时也能直接引用这些库,不必跳到新 skill。

**What**:在 L440-442 的表格追加 8 行,链接指向新 skill 的 cdn-catalog.md:

```markdown
| When clearly needed | Library |
|---|---|
| Charts (line / bar / pie) | Chart.js (`https://cdn.jsdelivr.net/npm/chart.js`) |
| Complex custom visualizations | D3 v7 (`https://d3js.org/d3.v7.min.js`) |
| 20+ chart types, K-line, heatmap, sankey | ECharts 5 (`https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js`) — see `skills/web-viz-libraries/references/embed-templates/echarts.html` |
| 3D scenes / objects / lighting | Three.js 0.160 (`https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.min.js`) — see `skills/web-viz-libraries/` |
| 2D physics (gravity / collision) | Matter.js 0.20 (`https://cdn.jsdelivr.net/npm/matter-js@0.20.0/build/matter.min.js`) |
| Vector maps (draggable / zoomable) | Mapbox GL JS 3.2 (需 token) — see `skills/web-viz-libraries/references/embed-templates/mapbox-dark.html` |
| 3D designs from community | Spline `<spline-viewer>` — see `skills/web-viz-libraries/` |
| 2D vector animations | Rive `@rive-app/canvas` — see `skills/web-viz-libraries/` |
| WebGL shader effects | Shadertoy boilerplate — see `skills/web-viz-libraries/references/embed-templates/shadertoy-boilerplate.html` |
| 2D no-code interactive effects | Unicorn Studio embed — see `skills/web-viz-libraries/` |
| Custom typography | Google Fonts (avoid Inter / Roboto / Arial / Fraunces / system-ui as display) |
```

**风险**:轻微内容重叠,但通过"链接到新 skill"而非"复制内容"避免重复维护。

---

## 假设与决策

1. **默认 `wait_ms=1000` 保持向后兼容** — 不破坏现有 render_pdf.py 调用方
2. **新 skill 包含全部 8 库** — 与用户原始需求清单一致,后续无需补
3. **新 skill 定位为"可视化库速查",不与 web-design-engineer 重叠** — web-design-engineer 管设计语言/排版/配色,新 skill 管可视化库的 CDN/嵌入/适用场景
4. **三种交付场景兼顾(PNG/PDF/交互 HTML)** — SKILL.md 每库标注三档适用性,LLM 按用户目标选库
5. **不改 render_html.py** — 它的 `wait_ms` 参数已存在(默认 1500ms),无需改
6. **不改 md-to-pdf 的 showcase 模板** — 自由设计模式下 LLM 直接 `write_file`,加 CDN 无障碍
7. **Mapbox token 由用户提供** — LLM 在 HTML 里写 `'YOUR_MAPBOX_TOKEN'` 占位,注释提示替换
8. **Spline/Rive/Unicorn 标注"需先在平台 Remix/下载"** — LLM 无法替用户操作平台,模板里留占位 URL

---

## 实施顺序

1. **改动 1(render_pdf.py)** — 改一个文件,5 处编辑,无依赖
2. **改动 2(web-viz-libraries skill)** — 新建目录 + 1 个 SKILL.md + 1 个 cdn-catalog.md + 1 个 decision-tree.md + 9 个 embed-template HTML
3. **改动 3(web-design-engineer CDN 表)** — 改一个文件,追加 8 行表格(可选,与改动 2 并行)

---

## 验证步骤

### 验证改动 1(render_pdf.py)

1. 跑现有 PDF 渲染,确认默认行为不变:
   ```
   python skills/md-to-pdf/scripts/render_pdf.py --html <现有测试 HTML> --out output/test1.pdf
   ```
   预期:成功生成 PDF,行为与改动前一致(默认 wait-ms=1000)。

2. 跑重型库 HTML,带 `--wait-ms 3000`:
   ```
   python skills/md-to-pdf/scripts/render_pdf.py --html output/echarts-test.html --out output/test2.pdf --wait-ms 3000
   ```
   预期:echarts 复杂图表完整渲染(PDF 内图表无空白/缺失)。

3. 跑 `--help` 确认新参数:
   ```
   python skills/md-to-pdf/scripts/render_pdf.py --help
   ```
   预期:看到 `--wait-ms` 参数及说明。

### 验证改动 2(web-viz-libraries skill)

1. 模拟 LLM 触发场景:对 LLM 说"帮我在网页里画一个柱状图" → 预期 LLM 读取 SKILL.md 决策树 → 选用 echarts → `read_file embed-templates/echarts.html` → `write_file output/chart.html` → `render_html(html_path="output/chart.html", wait_ms=1500)` 截图。

2. 每个 embed-template HTML 用浏览器直接打开,确认可见效果:
   - echarts.html:柱状图渲染
   - three-basic.html:旋转立方体
   - three-importmap.html:可旋转的立方体
   - matter-physics.html:球落体 + 鼠标拖拽
   - mapbox-dark.html:暗色地图(token 占位时会报错,但 HTML 结构正确)
   - spline-web-component.html:spline-viewer 元素加载(scene URL 占位时显示空)
   - rive-canvas.html:canvas 元素(.riv 占位时显示空)
   - shadertoy-boilerplate.html:WebGL canvas 默认渐变
   - unicorn-embed.html:占位 div(project ID 占位时显示空)

3. cdn-catalog.md 每个链接可访问(HTTP 200)。

### 验证改动 3(web-design-engineer CDN 表)

1. 读 [SKILL.md L434-449](file:///d:/project/workspace/skills/web-design-engineer/SKILL.md) 确认表格新增 8 行,链接路径正确指向 `skills/web-viz-libraries/`。

---

## 不做的事(明确边界)

- ❌ 不改 `render_html.py` — 它的 `wait_ms` 参数已够用
- ❌ 不改 md-to-pdf 的 showcase 模板 — 自由设计模式下 LLM 直接 `write_file` 即可
- ❌ 不新增 Python 依赖 — 前端库走 CDN,Python 侧只需 playwright
- ❌ 不在 render_pdf.py 里内置 CDN 白名单 — LLM 在 HTML 里自由挂载,render_pdf 只管渲染
- ❌ 不为动画类库(Matter.js/Rive/Spline)做"截图序列/GIF 导出" — 超出本次范围,如需可走 web-video-presentation skill
- ❌ 不写测试脚本 — render_pdf.py 的验证用现有 HTML 手动跑即可
