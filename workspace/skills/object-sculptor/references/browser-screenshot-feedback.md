# Browser Screenshot Feedback

Use this reference when a procedural Three.js reconstruction has an HTML preview under `output/`.

## Capture Rule

Each visual build pass should produce at least one rendered screenshot from a named review viewpoint.

**唯一允许的截图方式（DeepAgent）**：对 `sculpt.py package` / `package_html.py` 产出的 HTML 调用 **`render_html` 工具**。没有备选栈。

```text
render_html(html_path="output/<name>.html", wait_ms=2500)
```

Requirements for a usable capture:

- HTML must use `preserveDrawingBuffer: true` (the packager already sets this).
- Use `wait_ms` ≥ 2500 so Three.js finishes the first frames.
- Viewport should cover the full canvas (default desktop viewport is usually fine).
- Packaged HTML is a self-contained file; **do not** start `python -m http.server`, `npx serve`, or any port listener before capture.
- **Do not** background shells (`&` / `nohup`), install Playwright/Puppeteer/Chromium, or ask the user to open a browser for screenshots.
- Spec wording like `in-app-browser-screenshot` / `preferredCapture` means the `render_html` tool, not a local HTTP server.

If `render_html` fails, fix the HTML / retry the tool — do not invent a second capture pipeline.

Save or copy the PNG to `tmp/sculpt/<slug>/review/<pass>-render.png` for the compare step.

Create a side-by-side review image after capture:

```text
python skills/object-sculptor/scripts/sculpt.py compare --reference <reference.png> --render tmp/sculpt/<slug>/review/<pass>-render.png --out tmp/sculpt/<slug>/review/<pass>-comparison.png --manifest-out tmp/sculpt/<slug>/review/<pass>-evidence.json --diagnostics-dir tmp/sculpt/<slug>/review/<pass>-diagnostics --json
```

For a v4 module (advanced, not MVP default), also pass `--sculpt-manifest ... --module-id ...` so the evidence contains the required render receipt.

The script aligns and packages evidence, verifies real image inputs, and hashes the exact artifacts. It must not calculate the acceptance score.

**DeepAgent vision rule**: call the `view_image` tool on the reference, render, and `comparison.png` before scoring. A bare file path from `read_file` / tool text is not visual evidence. Requires `LLM_PROVIDER=siliconflow` (or `LLM_SUPPORTS_VISION=true` with a vision-capable model). The verdict must bind the comparison artifact hash from the evidence manifest.

When `--diagnostics-dir` is used, inspect the silhouette overlay and manifest metrics to correct camera/framing before geometry. Red is reference-only, cyan is render-only, and white is overlap. Missing/empty masks and gross silhouette/framing/detail mismatch are hard vetoes; good diagnostics still cannot unlock a pass.

The layout uses contain/no-crop fitting. For multi-view passes, use `--pairs-json` and `--manifest-out`; all required views go into one contact sheet and one immutable manifest.

## Compare By Layer

Review screenshot evidence in this order:

1. Silhouette and proportions: bounding shape, width/height/depth cues, taper, symmetry, negative space.
2. Component structure: parent/child placement, joints, contact points, repeated systems, floating or detached parts.
3. Form detail: bevels, chamfers, curvature, bends, dents, seams, raised ridges, holes, deformation scale.
4. Surface response: albedo zones, roughness variation, metalness, clearcoat, transmission, normal/bump/displacement, ambient occlusion.
5. Local features: scratches, chips, dirt accumulation, moss, stains, color patches, edge wear, contact wear.
6. Lighting/camera: exposure, shadow softness, contact shadows, color temperature, rim light, reflection readability.
7. Performance tradeoff: whether missing detail is intentional because of triangle, draw call, texture, or FPS budgets.

Action selection and root-cause rules live only in `self-correction-loop.md`. This file owns capture, evidence packaging, and visual scoring order.

## AI Vision Scorecard

Score each applicable layer from `0` to `1`, then assign one overall score based on the pass goal:

- `silhouetteProportion`: outer contour, mass distribution, negative space, camera-normalized proportions.
- `componentStructure`: hierarchy, placement, attachment, repeated systems, floating or disconnected parts.
- `formDetail`: taper, bend, bevel, deformation, secondary forms, local geometry.
- `materialSurface`: albedo, roughness, reflectance, normal/displacement, AO, local wear, tactile frequency.
- `lightingCamera`: camera match, exposure, key/fill/rim balance, shadow/contact response, background.

Do not hide a critical failed layer inside a high average. If a layer is essential to the current pass and remains visibly wrong, choose `refine-spec` or `refine-code` even when the arithmetic mean is above threshold; use one `refine-batch` when the complete fix spans both.

## Feature Tiers

- `critical`: identity-defining, user-prioritized, visually salient, or high-risk subsystem. It must be visible and pass independently; face/hand targets must also bind their dedicated `viewIds`.
- `important`: useful secondary subsystem. Review only suspicious items; the reviewed average must meet the configured threshold.
- `detail`: micro detail. Record mismatch notes and defer to refinement unless the user promotes it.

Repeated parts should be one target when they form one recognizable system. For example, review three cabins as `cabin-system`, not three separate cabin targets.

## Evidence Format

Record each item in `evidence.views` with:

- `viewId`: the required view name.
- `referenceImage`: source image, crop, or marked-up reference path.
- `renderScreenshot`: browser-rendered screenshot path.
- `comparisonImage`: side-by-side evidence image reviewed by AI vision.

Record review-level fields separately:

- `aiVisionScore`: overall score from `0` to `1`.
- `layerScores`: per-layer scores from the scorecard.
- `featureReviews`: critical/important feature scores.
- `--reviewer-model`: use `current` (or the actual provider model id) in DeepAgent.

## Runtime receipt (optional for MVP)

Upstream modular evaluate expects `window.__THREEJS_SCULPT_CAPTURE_RUNTIME__()`. The packaged HTML loads the generated factory (which installs that hook). MVP monolithic review can proceed with compare + vision scores without forcing a runtime JSON file unless you later enable `module evaluate`.
