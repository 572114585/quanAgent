# PPT Master Skill 集成方案

## 总结

- 将 `D:\codes\ppt-master\skills\ppt-master` 以完整快照方式集成到 `workspace/skills/ppt-master`，保留全部工作流、脚本、模板、许可证和赞助信息。
- 固定上游版本 `4.8.0`、提交 `cdabb4e5e0703651f88738df8b5f43eaee7fd50c`，增加来源与本项目适配记录，后续采用受控升级，不运行上游自更新脚本。
- 保持主模型为 DeepSeek；PPT 图片理解独立使用硅基流动 Qwen3-VL，图片生成只使用火山引擎 Seedream，不回退到国外模型。
- 第一阶段只支持 Web 端，保留独立的 localhost 确认/预览页面、单次长 SSE 流和可恢复项目状态。
- 组织方式遵循 Codex Skill 的 `SKILL.md + scripts/references/assets` 渐进加载结构。[OpenAI Build Skills](https://learn.chatgpt.com/docs/build-skills)

## 实施改动

### Skill 与工作目录

- 完整复制 PPT Master，并保留上游 `SKILL.md` 元数据、attribution guard 标记、`LICENSE`、`SPONSORS.md` 和 `SPONSORS_CN.md`。
- 在 Skill 中加入强制读取的 `references/quanagent-host.md`，规定：
  - 中间项目统一创建在 `workspace/tmp/ppt-master-projects`。
  - 最终 PPTX 必须显式输出到 `workspace/output/<安全文件名>.pptx`。
  - 图片检查调用新的国内视觉工具，不调用依赖主 LLM 的现有 `view_image`。
  - 图片生成后端只能为 Volcengine。
  -默认工作流使用独立确认页并在 Web 对话中返回可点击地址。
- 增加供应商元数据，记录上游版本、提交、来源和本地补丁；禁止直接运行 `update_repo.py` 覆盖适配层。
- 模板注册允许通过 PPT Master 官方注册脚本写入 `workspace/skills/ppt-master/templates/**` 及其索引；通用写文件工具仍禁止修改整个 `skills/`。升级前备份并合并用户模板和索引。

### 视觉能力

- 新增只读工具：
  `review_ppt_images(paths: list[str], task: str, detail: "low" | "high" = "high") -> str`
- 工具允许一次检查 1–8 张位于 `uploads/`、`tmp/`、`output/` 的图片，复用现有路径安全校验，并注册到主 Agent 和通用审阅子 Agent。
- 使用硅基流动 OpenAI-compatible 接口，默认模型固定为已验证在当前账号可用的 `Qwen/Qwen3-VL-30B-A3B-Instruct`，关闭 thinking；不改变全局 DeepSeek 配置。[硅基流动多模态视觉文档](https://docs.siliconflow.cn/cn/userguide/capabilities/multimodal-vision)
- PPT Master 图片生成配置为 `volcengine`，默认使用其现有 Seedream 4.5 实现。增加后端白名单校验，显式拒绝 OpenAI、Gemini 等后端；火山接口失败时返回明确错误，不静默切换。[火山引擎 Seedream 文档](https://www.volcengine.com/docs/6492/2221472?lang=zh)

### 执行、依赖与 Web 行为

- 将可信脚本发现从一层目录改为递归发现 `skills/*/scripts/**/*.py|sh`，使确认页和 SVG 编辑器等嵌套脚本可执行；仍拒绝 `tmp/` 或其他位置的任意脚本。
- 继续使用缩减后的子进程环境变量白名单，仅新增 PPT 所需变量，避免将其他密钥传给脚本。
- 根依赖加入 `-r workspace/skills/ppt-master/requirements.txt`。基本 PPT 生成不依赖 LibreOffice/Inkscape；ffmpeg、Pandoc、PowerPoint 视频导出作为可选能力，缺失时给出功能级提示，不阻塞 PPTX。
- 单次 Web 运行上限设为 3600 秒、递归上限 120；耗时的 `execute` 调用显式传入 3600 秒超时。
- 使用现有 SQLite checkpoint 和 `tmp/ppt-master-projects` 保存恢复状态，不新增后台任务队列。连接中断后可通过现有恢复执行入口继续。
- 最终 PPTX 进入 `workspace/output` 后沿用现有 artifact 检测和下载能力，不修改前端文件下载协议。
- 不为微信/企业微信开放命令执行能力。

## 配置与公开接口

新增或记录以下配置：

```dotenv
PPT_VISION_MODEL=Qwen/Qwen3-VL-30B-A3B-Instruct
PPT_VISION_TIMEOUT=120
PPT_VISION_MAX_TOKENS=2000

IMAGE_BACKEND=volcengine
PPT_ALLOWED_IMAGE_BACKENDS=volcengine
IMAGE_CONCURRENCY=2
LAS_API_KEY=

AGENT_RUN_DEADLINE_SECONDS=3600
AGENT_RECURSION_LIMIT=120
```

- 视觉理解复用现有 `SILICONFLOW_API_KEY` 和 `SILICONFLOW_BASE_URL`。
- Seedream 使用新配置的 LAS 专用 `LAS_API_KEY`；不依赖当前无法通过 Ark 模型接口认证的 `VOLCENGINE_API_KEY`。
- 修改 `.env.example` 和配置说明；本地 `.env` 只补充必要项，不输出或提交密钥。
- 对当前已有的 MOSS、提示词、依赖和沙箱改动进行增量合并，不覆盖工作区中的用户修改。

## 测试与验收

- 单元测试覆盖 Skill 发现、attribution guard、嵌套可信脚本、任意脚本拒绝、环境变量白名单、视觉请求格式、路径及图片数量限制、国内图片后端锁定和 PPTX artifact 识别。
- 使用 mock 验证 Qwen3-VL 请求、超时和错误处理；账号额度允许时执行一次小图实时视觉识别。
- 启动并检查确认页和 SVG 编辑器的健康检查、阶段切换及关闭流程。
- 执行最小三页 Quick 工作流：项目位于 `tmp`，完成 SVG 检查、PPTX 导出、postflight，并验证文件为可打开 ZIP 且页数正确。
- 分别冒烟验证 Default Generate、Create Template、Fill Native PPTX、Enhance Native PPTX；确认模板注册只能通过可信脚本写入指定目录。
- 在 `LAS_API_KEY` 配置完成后仅执行一次计费的 16:9 Seedream 4.5 图片生成测试，验证尺寸和文件可读性；认证失败不自动重试或切换供应商。
- Web 验收标准：
  - “快速生成 3 页……”能返回可下载 PPTX。
  - 默认流程能打开独立确认页，确认后在同一 SSE 运行中继续。
  - 日志中视觉审阅只出现硅基流动 Qwen3-VL，图片生成只出现火山 Seedream。
  - 中断或重启后可从 checkpoint 和临时项目继续，不丢失已生成页面。
