# QuanAgent Host Contract

Read this document for every PPT Master route after `SKILL.md` and before any
workflow action. It is the local adaptation layer for the locked upstream
snapshot; upstream workflow documents remain authoritative where this document
does not say otherwise.

## Paths and artifacts

- Create every intermediate project under
  `workspace/tmp/ppt-master-projects/<safe-project-name>/`.
- The final deck must be written explicitly to
  `workspace/output/<safe-file-name>.pptx`. Do not leave a final PPTX only in
  a project directory.
- Only the official `scripts/register_template.py` may add or rebuild template
  records under this package's `templates/**` and indexes. General file tools
  must not modify `workspace/skills/`.
- `scripts/update_repo.py` is disabled in this vendored copy. Upgrade by making
  a backup, importing a reviewed upstream snapshot, then merging user templates
  and indexes deliberately.

## Domestic visual providers

- For image inspection use `review_ppt_images`, never `view_image`. It is an
  isolated SiliconFlow Qwen/Qwen3-VL-30B-A3B-Instruct review service.
- Image generation is locked to `IMAGE_BACKEND=volcengine`, using Agent Plan
  `doubao-seedream-5.0-lite` with `AGENT_API_KEY` and
  `ARK_AGENT_PLAN_BASE_URL=https://ark.cn-beijing.volces.com/api/plan/v3`.
  Never select or fall back to OpenAI, Gemini, or another provider. A
  Volcengine error is terminal for that image attempt and must be reported
  clearly.

## Web confirmation and recovery

- The default ordinary business-deck flow is **Fast Generate**. It does not
  start `confirm_ui`, `svg_editor`, live preview, a first-page check, or
  `finalize_svg.py`. Create one `fast_contract.json`, then call
  `ppt_fast_build(project_path)`. It uses four one-shot page workers, at most
  three Seedream image tasks, one lockless final checker, one Qwen whole-deck
  visual review, at most one parallel repair pass, and safe editable slide
  fallbacks. Its deadline is 300 seconds and its final record is
  `validation/fast_run.json`.
- Select an existing dedicated route instead when the request requires a
  confirmation page, real-time preview or annotation, complex animation,
  narration/video, pixel-faithful reconstruction, native Master/Layout, or a
  custom template refinement. Those routes make no five-minute promise.
- Fast workers receive only the compact contract, assigned slides, the
  `presentation_core` prototype, and declared resources. Do not load the
  complete Quick reference set or enter a `task()` subgraph/checkpoint.
- Image failures and page timeouts are terminal for that enhancement only:
  keep the pre-existing native visual layer and use the contract's editable
  safe layout. Never switch image providers or retry indefinitely.
- Keep resumable state in the existing SQLite checkpoint and the project
  directory above. Do not create a background task queue.
- Pass `timeout=3600` to long-running `execute` calls. Optional capabilities
  (LibreOffice, Inkscape, ffmpeg, Pandoc, and PowerPoint video export) may emit
  a capability-level notice when unavailable but must not block a basic PPTX.
