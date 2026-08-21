# PPT Master 5 分钟 Fast 链路改造

## Summary

目标：普通 10–12 页、16:9、无音视频/复杂动画的商务 PPT，从请求开始到生成通过 postflight 的本地可下载 PPTX，硬上限 300 秒。

当前实测默认链路约 20 分钟，主要耗时来自双人工确认、超大提示上下文、图片失败重试和主 Agent 串行逐页创作。改造后的主链路为：

`资料/主题 → Fast Contract → 4 个页面 Worker + 最多 3 张图片并行 → 静态检查 → Qwen 整套视觉审阅 → 一轮并行修复/安全降级 → PPTX`

## Implementation Changes

### 1. 默认 Fast 路由与界面精简

- 新增 QuanAgent 专用 `Fast Generate` profile，普通“制作 PPT”默认进入；现有慢速 Default、Quick、Beautify、Image-to-PPTX、Fill、Enhance 能力继续保留。
- 明确要求人工确认、实时预览、批注、复杂动画/旁白/视频、高保真复刻、原生 Master/Layout 或自定义模板精修时，路由到现有专用链路，不承诺 5 分钟。
- Fast 不启动 `confirm_ui` 和 `svg_editor`，不执行首屏确认、首屏 checker 或 `finalize_svg.py`。
- 从聊天界面移除 `FloatingTodoList` 实时任务/子 Agent 看板；后端 `todos`、任务事件和可靠性 middleware 保留给 AI 内部使用，现有 SSE/API 字段保持兼容。
- 保留消息级最终总耗时显示，不展示逐任务实时进度。

### 2. 紧凑契约与真正并行创作

- Fast 项目只生成一个 `fast_contract.json`，作为内容、设计和并行分工的唯一共享契约；不生成 `design_spec.md`、`spec_lock.md` 或确认页文件。
- 契约固定包含：画布、配色、字体、输出名、来源、最多 12 页 roster、每页角色/核心信息/布局键、类型化内容块、资源引用及最多 3 个图片任务。
- 默认使用现有 `presentation_core` 版式原型；页面 Worker 获得全局设计令牌、自己负责的 2–3 页、所选原型 SVG 和资源清单，不加载当前约 100K token 的完整 Quick 参考集。
- 新增 `ppt_fast_build(project_path)` 工具：
  - 使用当前主模型建立 4 个无 checkpoint、一次性页面请求并通过 `asyncio.gather` 并发执行。
  - 每个 Worker 只能返回自己分配的文件；工具校验文件名、SVG/XML、画布和资源路径后原子写入 `svg_output/`。
  - Worker 不进入 DeepAgents `task()` 子图，避免实时看板事件和数百 MB 子图 checkpoint。
  - 图片 manifest 与页面 Worker 同时执行，最多 3 张、并发 3；统一使用 Web 服务的 `sys.executable`，避免当前不同 Python 环境导致的 `requests`/Pillow 缺失。
- Fast 时间预算固定为：契约与资料 45 秒、并行页面/图片 110 秒、静态与视觉 QA 60 秒、修复/降级与导出 55 秒、30 秒缓冲。
- 新增配置：`PPT_FAST_DEADLINE_SECONDS=300`、`PPT_PAGE_CONCURRENCY=4`、`PPT_PAGE_TIMEOUT_SECONDS=100`、`PPT_IMAGE_LIMIT=3`、`PPT_IMAGE_CONCURRENCY=3`、`PPT_FAST_VISION_TIMEOUT=35`。

### 3. AI 审阅、降级和导出

- 页面完成后仅运行一次 Quick final checker；不重复执行 first-page gate。
- 将全部页面无服务化渲染为 PNG，并按每张最多 6 页生成两张可读 contact sheet；不启动 localhost 实时预览服务。
- 使用现有 Qwen PPT 视觉工具一次审阅整套页面，只将空白页、缺图、裁切、重叠、溢出、严重对比度或可读性问题视为阻塞项。
- 阻塞页最多进行一轮并行修复；普通审美建议只记录，不进入无限迭代。
- 图片超时或失败时移除图片增强层，保留预先存在的原生背景/图形；页面 Worker 超时、输出无效或修复后仍阻塞时，按 `fast_contract.json` 的类型化内容块生成安全、可编辑的标准布局。
- 最终重新运行一次 checker，并直接执行 `svg_to_pptx --quick-generate --no-notes`；要求零 blocking issue、PPTX ZIP 可打开、页数正确、资源完整且 postflight 通过。
- 写入 `validation/fast_run.json`，记录每阶段耗时、并发数、图片结果、AI 审阅、修复和降级项；外部 MOSS 上传设置短超时并保持本地下载链接兜底。
- 修复 prompt audit 的本地根目录适配：加载 `quanagent-host.md`，移除不存在的 `AGENTS.md` 依赖，并同步新 Fast profile 的 load set 和 token budget。
- 修复 checkpoint 维护命令：先用 SQLite backup API 备份，只清理已完成且无 pending interrupt 的非空子图 namespace；根 checkpoint 不删除。历史数据库清理作为一次离线迁移执行。

## Public Interfaces

- 新增内部工具：`ppt_fast_build(project_path: str) -> FastBuildSummary`。
- 新增项目契约：`fast_contract.json`，schema 为 `quanagent.ppt-fast.v1`。
- 新增运行报告：`validation/fast_run.json`。
- 普通 Generate 的默认路由从交互式 Default 改为 Fast；显式精修和高级能力仍使用原路由。
- `/chat`、`/chat/resume`、todos、subagent SSE 事件和 artifact 下载协议保持兼容；仅移除任务看板的前端呈现。

## Test Plan

- 单元测试覆盖 Fast 路由、契约 schema、路径穿越、重复文件、12 页和 3 图上限、4 路唯一分工及原子写入。
- 使用延迟 Fake LLM 验证 4 个 Worker 真正并发，Mock P90 总耗时小于 300 秒，并验证单 Worker 超时不会阻塞其他页面。
- 验证图片生成使用同一解释器、并发 3、无跨供应商回退；失败后自动保留原生视觉层。
- 验证静态 contact sheet 不依赖确认页或实时 SVG 服务，Qwen 仅触发一轮阻塞项修复。
- 验证缺页、无效 SVG、资源缺失和修复失败均进入安全布局，最终仍为可打开、可编辑且零 blocking issue 的 PPTX。
- 验证 Fast 全程不创建 confirm/live-preview、first-page report、`svg_final/` 或子 Agent checkpoint。
- checkpoint 测试验证备份可恢复、根历史和 pending interrupt 不变、已完成子图可安全删除。
- 前端生产构建验证移除任务看板后聊天、审批、工具记录、最终耗时和附件下载正常。
- 最后使用现有 10 页案例执行 1 次真实 DeepSeek + Qwen + 最多 3 张 Seedream 端到端验收；其余并发、超时和 P90 场景使用完整 Mock 基准。

## Assumptions

- 5 分钟承诺适用于 10–12 页标准稿、已有资料或可通过一次快速搜索补齐的主题、最多 3 张生成图片。
- 速度优先时允许对失败图片或页面使用安全、可编辑的原生布局，并在最终结果中列明降级项。
- 音频、视频、复杂动画、高保真逐像素复刻、自定义原生 Master/Layout 和人工交互精修不纳入 5 分钟 SLO。
- SLO 以本地 PPTX 写入 `workspace/output` 且 postflight 通过为终点；外部公网存储上传不得阻塞本地交付。
