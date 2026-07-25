---
name: object-sculptor
description: "把参考物体图片重建为可交互的程序化 Three.js 模型（代码即资产，非摄影测量）。用户上传物体参考图并要求做成 3D/可旋转预览/动画就绪道具时使用。输出 ObjectSculptSpec + Three.js factory + output/*.html。不用于扫模、GLB 下载、或 PDF 内嵌 WebGL。"
allowed-tools: execute read_file write_file edit_file render_html view_image ask_user_question inspect_file
---

# Object Sculptor — 图 → 程序化 Three.js

基于上游 [Three.js Object Sculptor](https://github.com/vinhhien112/Three.js-Object-Sculptor-Codex-Plugin)（MIT）改编的 DeepAgent Skill。  
**不是**摄影测量 / 精确扫模；而是按雕塑流程写几何代码，并用截图 + 视觉对比做质量门禁。

## 前置条件（Vision）

本 skill **依赖多模态视觉模型**。推荐：

```env
LLM_PROVIDER=siliconflow
SILICONFLOW_API_KEY=...
SILICONFLOW_MODEL=Qwen/Qwen3.6-35B-A3B
# siliconflow 默认 LLM_SUPPORTS_VISION=true；其他 provider 需显式打开
```

- 用户上传的参考图：Web 在 vision 开启时会以 `image_url` 送入模型。
- 中间产物（render / comparison）：**必须**用 `view_image(path)` 加载后再打分；`read_file` 路径字符串**不能**代替看图。
- 若 `view_image` 报不支持 vision：停止流程，告知用户切换 siliconflow 或设置 `LLM_SUPPORTS_VISION=true`。

## 何时使用

| 场景 | 用本 skill? |
|---|---|
| 用户给了物体参考图，要做成可旋转/可交互的 Three.js 模型 | ✅ |
| 要动画就绪 pivot/socket 的实时道具 | ✅ |
| 只要随便一个 3D 立方体/简单场景（无参考图） | ❌ 用 `web-viz-libraries` |
| 用户只要 PDF 文档里的 3D | ❌ WebGL 不进 PDF；可截 PNG 再嵌入 |
| 要精确 mesh / GLB 扫模 | ❌ 能力范围外 |

## 硬性约束（DeepAgent）

1. **命令必须单行**：`execute(command=...)` 禁止反斜杠续行。
2. **工作目录是 workspace 根**：脚本路径用 `skills/object-sculptor/scripts/...`。
3. **可写目录**：中间文件 → `tmp/sculpt/<run-id>/`；交付物 → `output/`。
4. **只跑本 skill 自带脚本**（白名单）；不要自写 `.py` 再 execute。
5. **MVP 默认**：`--layout monolithic` + `--quality-profile balanced`；只跑 `blockout → form → lookdev`，视觉修正最多 **2 轮**。未经用户要求不要开 v4 modular / PBR / destructible 全流程。
6. **交付形态**：`output/<name>.html`（交互预览）+ 可选 PNG 截图。不要承诺进 PDF。
7. **视觉评审前必须 `view_image`**：参考图、render PNG、comparison PNG 都要加载。
8. **截图唯一路径 = `render_html` 工具**（对 `output/<name>.html`）。禁止用 `execute` 起任何常驻服务或第二套浏览器，包括但不限于：
   - `python -m http.server` / `npx serve` / `live-server` / 任意 listen 端口
   - shell 后台（`&`、`start /b`、`nohup`）与「起服务再 curl/截图」
   - 安装或调用 Playwright / Puppeteer / Selenium / Chromium
   - `file://` 手开浏览器、让用户手动截图（除非用户主动提供已有 PNG 路径）
   Spec 里的 `preferredCapture` /「browser screenshot」均指调用 **`render_html` 工具**，不是自己起 HTTP 服务。

## 命令面

```text
python skills/object-sculptor/scripts/sculpt.py <command>
```

| 命令 | 用途 |
|---|---|
| `init` | 创建 monolithic Spec |
| `probe` | 检查参考图基本属性 |
| `validate` | 校验 Spec（可加 `--for-pass` / `--strict-quality`） |
| `status` / `sync` / `check` | 查看当前 pass 是否可生成 |
| `generate` | 从 Spec 生成 `*.generated.ts` factory |
| `package` | TS factory → 独立 HTML（DeepAgent 交付） |
| `compare` | 参考图 vs 渲染截图 → 对比图 |
| `review` | 记录视觉评审结果 |
| `module` / `pbr` / `views` | 进阶（MVP 默认不用） |

`package` 也可直接调用：

```text
python skills/object-sculptor/scripts/package_html.py --factory <ts> --out output/<name>.html --title "<标题>"
```

## MVP 工作流

约定 run 目录：`tmp/sculpt/<slug>/`（例如 `tmp/sculpt/oak-tree/`）。

### 1. 确认输入与档位

- 需要至少一张可检查的参考图（上传文件路径，常见在 `uploads/` 或用户给出的路径）。
- 缺 intended-use 时默认 `browser-prop`；复杂度不清时从 `moderate` 起，看图后可改。
- 若用户未说明是否精修，可用 `ask_user_question` 问：快速预览（1 轮）还是精修（最多 2 轮视觉修正）。

### 2. Init Spec（monolithic）

```text
execute(command="python skills/object-sculptor/scripts/sculpt.py init \"物体名\" --image <参考图路径> --complexity moderate --intended-use browser-prop --quality-profile balanced --layout monolithic --out tmp/sculpt/<slug>/object-sculpt-spec.json")
```

### 3. 目视填 Spec（必须）

`init` 只给骨架。在 `generate` 前用 `read_file` + `write_file`/`edit_file` 填完：

- `preSpecAssessment.objectClass`（primaryType / formLanguage / structureKind / materialFamilies 等）
- `preSpecAssessment.specializedRegions`（无脸/手 → `status: none` + reason）
- `silhouette`（boundingShape / aspectRatios / dominantCurves）
- 几何组件、材质、层级（见 `references/procedural-patterns.md`、`references/pre-spec-assessment.md`）

然后：

```text
execute(command="python skills/object-sculptor/scripts/sculpt.py validate tmp/sculpt/<slug>/object-sculpt-spec.json --for-pass blockout --strict-quality")
```

修到无 error 再继续。

### 4. 生成 factory → 打包 HTML

```text
execute(command="python skills/object-sculptor/scripts/sculpt.py generate tmp/sculpt/<slug>/object-sculpt-spec.json --out tmp/sculpt/<slug>/Object.generated.ts --wrapper-out tmp/sculpt/<slug>/Object.ts")
```

```text
execute(command="python skills/object-sculptor/scripts/sculpt.py package --factory tmp/sculpt/<slug>/Object.generated.ts --out output/<name>.html --title \"物体名\"")
```

HTML 使用 Three.js **0.160** importmap（与 `web-viz-libraries` 一致），且 `preserveDrawingBuffer: true`。

### 5. 视觉闭环（仅 render_html + compare + view_image + 评审）

对每个需要验收的 pass（MVP：`blockout` / `form` / `lookdev`）：

1. **只用工具截图**（`wait_ms≥2500`）。禁止 `http.server` 等替代方案：

```text
render_html(html_path="output/<name>.html", wait_ms=2500)
```

将返回的 PNG 复制到 `tmp/sculpt/<slug>/review/<pass>-render.png`（若工具已写出路径，直接用该路径）。`package` 后的 HTML 已是独立文件，**不需要**本地静态服务器。

2. 对比：

```text
execute(command="python skills/object-sculptor/scripts/sculpt.py compare --reference <参考图> --render tmp/sculpt/<slug>/review/<pass>-render.png --out tmp/sculpt/<slug>/review/<pass>-comparison.png --manifest-out tmp/sculpt/<slug>/review/<pass>-evidence.json --diagnostics-dir tmp/sculpt/<slug>/review/<pass>-diagnostics --json")
```

3. **用 `view_image` 加载后再评审**（勿假设路径字符串等于看见图像）：

```text
view_image(path="<参考图路径>")
view_image(path="tmp/sculpt/<slug>/review/<pass>-render.png")
view_image(path="tmp/sculpt/<slug>/review/<pass>-comparison.png")
```

按 `references/browser-screenshot-feedback.md` 与 `references/self-correction-loop.md` 打分。脚本**不会**自动打分。

4. 记录结果：

```text
execute(command="python skills/object-sculptor/scripts/sculpt.py review tmp/sculpt/<slug>/object-sculpt-spec.json --pass-id <pass> --fidelity <0-1> --action <continue|refine-code|refine-spec|stop> --summary \"...\" --evidence-set-json tmp/sculpt/<slug>/review/<pass>-evidence.json --ai-vision-score <0-1> --reviewer-model current --in-place")
```

5. 若 `refine-*`：改 Spec 或手写包装代码 → 重新 `generate` → `package` → 截图对比。同一 pass 最多 **2** 轮修正；仍不够则说明限制并交付当前最佳 HTML，或 `ask_user_question` 是否继续。

### 6. 交付

- 主产物：`output/<name>.html`（前端 artifact iframe 可预览）
- 可选：`render_html` 的 PNG、Spec JSON 副本到 `output/`
- 在回复中说明：这是程序化近似，非扫模；隐藏面/玻璃/毛发等可能简化

## Pass 目标（自适应）

| Pass | 目标 |
|---|---|
| `blockout` | 剪影、比例、主块面 |
| `form` | 可识别几何与局部形体 |
| `lookdev` | 材质、光照、接触阴影可读 |
| `structure` / `interaction` / `optimization` | 仅复杂或动画/游戏用途时启用（MVP 默认跳过） |

## 降级与拒绝

- 参考图不适合（严重遮挡、纯纹理无形体、多物体混杂）→ `probe` 后说明并拒绝或要求更好参考图
- 透明玻璃 / 烟雾 / 毛发 / 精细布料 → 明确告诉用户将用有界近似，或降低 fidelity
- 单图无法看到的背面 → 标注为假设，不要假装观测到

## 参考文档（按需读，勿一次全读）

| 需要 | 文件 |
|---|---|
| 复杂度与质量契约 | `references/pre-spec-assessment.md` |
| 程序化几何套路 | `references/procedural-patterns.md` |
| 截图 / compare / 评分层 | `references/browser-screenshot-feedback.md` |
| 修正动作与停止条件 | `references/self-correction-loop.md` |
| 材质光照 | `references/material-lighting-realism.md` |
| 动画就绪层级 | `references/action-ready-models.md` |
| 术语 | `references/3d-graphics-terminology.md` |

路径相对本 skill：`skills/object-sculptor/references/...`。

## 与 web-viz-libraries 的分工

- **有参考图且要程序化重建物体** → 本 skill
- **无参考图、只要图表/简单 3D/物理/地图** → `web-viz-libraries`

## 署名

上游：Vinh Hiển / Three.js-Object-Sculptor-Codex-Plugin（MIT）。见本目录 `LICENSE` 与 `ATTRIBUTION.md`。
