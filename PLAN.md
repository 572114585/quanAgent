# feature/v1 精简与提速计划

## Summary

本分支收敛为“通用 Agent + 快速联网搜索 + 文档/文件能力”：

- 完整移除知识库和 Research V2。
- 保持单一 `requirement.txt`，只删除废弃依赖，不拆文件。
- 所有联网查询统一走 Fast Search。
- 普通搜索只返回 3 条摘要；仅在用户提供 URL 或明确要求打开网页时抓取单页正文。
- 移除未使用的 SSE 事件持久化。
- 保留完整对话历史，但压缩 checkpoint 中间状态。
- 保留 `workspace/aiindex`、`workspace/uploads` 和旧 Research 数据；只删除生成的 `workspace/kb_store`。

## Implementation Changes

### 1. 移除知识库与 Research V2

- 删除知识库工具、管理 CLI、Chroma 初始化、KB 配置、权限规则、提示词、前端 `KB_REFS` 解析和知识库引用面板。
- 删除 Research V2 核心模型、工具、citation verifier、Research REST API、前端 Research 工作台、research-agent 子智能体及专属测试/评测。
- 删除 `research-strategies` skill；改写 `document-builder`、`outline-planner`、`section-writer` 和 `auto-review`，取消 run_id、Evidence ID、Coverage Matrix 和 report-ready 依赖。
- 文档任务改为最多执行 3 次快速搜索，将标题、URL、摘要写入 `/tmp/source_brief.md`；章节撰写直接使用 Markdown 链接引用。资料不足时明确标注缺口，不生成未经摘要支持的确定性事实。
- 保留通用 `check_final_report`，继续检查占位符、TODO、引用链接、关键点和过时预测。
- 从单一 `requirement.txt` 删除 `chromadb`、`rank_bm25`、`jieba`、`sentence-transformers`；其余依赖结构不变。
- 删除 `workspace/kb_store`；不删除 `workspace/aiindex`、`workspace/uploads`。`workspace/state/research` 保留为只读旧数据，运行时不再扫描或创建。

### 2. 建立唯一的快速联网链路

- 主 Agent 直接注册 `web_search` 和 `web_fetch`，联网不再委托子智能体。
- `web_search` 接口收敛为：
  - `query`
  - `max_results=3`，服务端强制限制为 1–5
  - `topic="general"|"news"`
- 删除 `mode`、`save_to`、`phase`、`search_depth` 及 fusion 排序；Provider 固定按 Tavily → Brave → Serper → DuckDuckGo 顺序 failover，首个非空结果立即返回。
- 每个 Provider 超时 6 秒；额度错误继续进入冷却；DDG 同样受 6 秒调用上限约束。成功后不再等待其他 Provider，也不自动抓取结果正文。
- Provider 复用 HTTP 连接池，并在应用 lifespan 结束时关闭。
- `web_fetch` 收敛为 `url`、`max_content_chars=6000`：
  - 仅当用户提供 URL 或明确要求打开/读取页面时允许调用。
  - Direct 请求一次，超时 8 秒；失败后仅尝试一次 Jina，超时 8 秒。
  - 不自动启用 Playwright。
  - 远程 PDF 不进入 MinerU 长链路，提示用户上传文件；上传文档仍可使用现有 MinerU skill。
- 保留 `WEB_REFS` 输出协议和前端联网引用展示。
- 系统提示词规定普通联网问题只执行一次搜索；同义改写和补搜仅在第一次无结果时执行一次。
- 将活动配置调整为 `LLM_MAX_RETRIES=3`、`AGENT_RECURSION_LIMIT=40`、`AGENT_RUN_DEADLINE_SECONDS=300`；thinking 保持关闭。

### 3. 精简启动和工具装配

- 将 `tools/__init__.py` 改为无 eager re-export 的轻量包入口，所有调用方从具体模块导入。
- Agent 启动只装配当前使用的通用工具、快速搜索工具、section-writer 和 general-purpose 子智能体。
- 删除 Research/KB 相关循环导入兼容代码、特殊工具输出分支和恢复审批桥接。
- 保留所有非 Research 类技能和 PDF、Word、Excel、图表、文件处理能力。
- 增加启动 smoke benchmark，确认导入阶段不会出现 `chromadb`、`sentence_transformers`、Research V2 或 Hugging Face 网络访问。

### 4. 移除事件日志并压缩 checkpoint

- 删除 `EventLog`、`events.sqlite` 配置、`GET /chat/events` 和前端未使用的 `fetchEvents`。
- SSE 事件继续在内存中携带 runId/eventId，但不再逐 token 写数据库。
- 不再生成空 `thinking` 事件；只有真实 reasoning 文本才发送 `thinking_delta`。
- 保留 `/chat/messages`、`/chat/sessions` 和最新 checkpoint，刷新后历史恢复方式不变。
- 新增离线状态维护命令：
  - 操作前使用 SQLite backup API 备份 checkpoint 和旧 event DB。
  - 有 pending interrupt 的 thread 完全不裁剪。
  - 已完成 thread 保留最近 3 个根 checkpoint，删除已完成子图 checkpoint 和未被保留 checkpoint 对应的 writes。
  - 校验每个 thread 最新 checkpoint blob 未变化后执行 WAL checkpoint 和 `VACUUM`。
  - 旧 `workspace/state/research` 明确排除在维护范围外。
- 后续每个成功且无 interrupt 的 run 结束后，后台执行同样的单 thread 裁剪；`VACUUM` 只由离线维护命令执行。
- 删除现有 `events.sqlite`、WAL、SHM 前先纳入一次性备份。

## Public Interface Changes

- 移除全部 `/research/*` API。
- 移除 `GET /chat/events`。
- 移除 `kb_search`、`kb_add_document`、Research V2 工具和 `KB_REFS` 前端类型。
- 简化 `web_search` 和 `web_fetch` 参数；保留 `WEB_REFS`。
- `/chat`、`/chat/resume`、`/chat/messages`、`/chat/sessions`、上传和产物接口保持兼容。
- `/chat/resume` 仍用于文件写入、Shell 等 HITL 审批，但删除 Research 计划批准逻辑。
- 前端不增加搜索模式开关，所有聊天统一使用快速搜索。

## Test Plan

- 单元测试验证首个 Provider 成功后不会调用后续 Provider，空结果/超时/额度错误才 failover，结果最多 3 条。
- 验证普通搜索不调用 `web_fetch`；显式 URL 请求按 Direct → Jina 执行，正文不超过 6000 字符，SSRF 防护保持有效。
- 验证运行时工具表、提示词、OpenAPI 和前端路由中不存在 KB/Research V2。
- 验证服务启动不导入 ML/向量库模块、不访问 Hugging Face、不创建 `kb_store`、`research` 或 `events.sqlite`。
- 用临时 SQLite 数据验证 checkpoint 裁剪：完整消息历史可恢复、pending interrupt 不变、孤立 writes 被删除、重复运行幂等、备份可恢复。
- 前端执行类型检查和生产构建，确认知识库引用面板及 Research 页面移除后聊天、联网引用和历史加载正常。
- 保留并运行通用权限、搜索、抓取、SSE、CLI、文档质量和文件工具测试；删除或替换所有只服务于 KB/Research V2 的测试与 eval。
- 一次性迁移后逐个验证现有 33 个会话仍可通过 `/chat/messages` 加载，再比较 checkpoint 数据库体积；验收要求历史会话无丢失且数据库明显缩小。

## Assumptions

- 快速和低延迟优先于多源融合、证据账本和自动深度抓取。
- 搜索摘要及其 URL 是联网回答的唯一默认资料；需要正文时由用户明确触发。
- 旧 Research 数据只作为离线归档保留，不提供兼容读取 API。
- 不主动删除或覆盖当前工作区中的原始资料和无关未提交改动。
- 依赖始终保留在一个 `requirement.txt` 中；环境体积清理由后续重建 `.venv` 完成。
