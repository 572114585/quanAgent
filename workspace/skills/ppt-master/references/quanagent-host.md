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

- The default flow starts the independent localhost confirmation page. Return
  its clickable localhost URL in the Web conversation and keep the same SSE run
  waiting for its result; use chat-only confirmation only on explicit request.
- Keep resumable state in the existing SQLite checkpoint and the project
  directory above. Do not create a background task queue.
- Pass `timeout=3600` to long-running `execute` calls. Optional capabilities
  (LibreOffice, Inkscape, ffmpeg, Pandoc, and PowerPoint video export) may emit
  a capability-level notice when unavailable but must not block a basic PPTX.
