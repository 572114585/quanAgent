"""Agent Web Bridge —— 把 agent_core 的 deep agent 暴露为 HTTP + SSE 端点。

（原根级 run.py 主体，迁移到 entrypoints/web.py；根级 run.py 保留为薄 shim）

启动：
    python run.py            # 默认 8000 端口
    PORT=9000 python run.py  # 自定义端口

调用方：agent-frontend（Vue 3 + Tauri 2），设置面板填 http://localhost:8000。

端点：
    GET  /health        健康检查
    POST /upload        上传文件（图片/文档），返回可访问的 URL
    POST /chat          发起/继续对话，返回 SSE 流
    POST /chat/resume   HITL 中断后，提交批准/拒绝决定，返回 SSE 流
    GET  /uploads/<f>   静态文件服务（供 /upload 返回的 URL 访问）

事件格式（与 src/types/domain.ts 的 StreamEvent 对齐）：
    data: {"type":"start","messageId":"..."}
    data: {"type":"delta","delta":"..."}                              ← 最终答案 token（无 tool_call_chunks 的 AIMessageChunk）
    data: {"type":"thinking_delta","delta":"..."}                    ← 思考过程 token（reasoning_content 或工具调用轮的过渡语）
    data: {"type":"thinking"}                                        ← 思考开始标记
    data: {"type":"tool_call","callId":"...","name":"...","args":...,"subagentId"?: "..."}  ← 模型决定调工具（subagentId 非空=子智能体内部步骤）
    data: {"type":"tool_result","callId":"...","name":"...","output":...,"subagentId"?: "..."}  ← 工具执行返回
    data: {"type":"subagent_start","subagentId":"...","subagentType":"...","description":"..."}  ← 子智能体 task() 启动
    data: {"type":"subagent_done","subagentId":"..."}                ← 子智能体 task() 结束
    data: {"type":"tool","name":"...","args":...,"preview":"..."}    ← 旧协议兼容（降级路径）
    data: {"type":"interrupt","groups":[{"interruptId":"...","toolCalls":[{"name":"...","args":{...}}]}]}
    data: {"type":"usage","promptTokens":N,"completionTokens":M}
    data: {"type":"done","messageId":"..."}
    data: {"type":"error","message":"..."}

设计原则：
    - 复用 agent_core.build_agent() 统一装配（与 CLI/channel 共享同一 agent 定义）
    - 工具调用分片累积只在 _stream_agent 里做；流式只把 ToolMessage 完整体推给前端
    - 思考 vs 最终答案：基于消息结构判断，不依赖模型输出文本标记
      · reasoning_content / 工具调用轮的 content → thinking_delta（折叠区）
      · 无 tool_call_chunks 的 AIMessageChunk content → delta（最终答案区）
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import json
import logging
import mimetypes
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, SystemMessage, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# === 复用 agent_core：build_agent 工厂 + 配置常量 ===
load_dotenv()

from agent_core import build_agent  # noqa: E402
from agent_core.config import (  # noqa: E402
    AGENT_API_TOKEN,
    AGENT_MODE_DEFAULT,
    AGENT_RECURSION_LIMIT,
    AGENT_RUN_DEADLINE_SECONDS,
    ALLOWED_ORIGINS,
    HITL_ENABLED_DEFAULT as HITL_ENABLED,
    LANGFUSE_ENABLED,
    LOG_LEVEL,
    MAX_UPLOAD_SIZE,
    OUTPUT_DIR,
    UPLOADS_DIR,
    WEB_HOST_DEFAULT,
)
from agent_core.events import SCHEMA_VERSION, make_event, make_event_id  # noqa: E402
from agent_core.permissions import AgentMode  # noqa: E402
from agent_core.run_registry import RunConflictError, get_run_registry  # noqa: E402
from agent_core.runtime import get_checkpointer  # noqa: E402
from artifacts import detect_new_artifacts, snapshot_output_dir  # noqa: E402
from tools.search import close_providers  # noqa: E402

try:
    if not LANGFUSE_ENABLED:
        raise ImportError("Langfuse tracing is disabled or unconfigured")
    from langfuse.langchain import CallbackHandler as _LangfuseCallbackHandler
except Exception:  # langfuse 未安装、未配置或被显式禁用时降级
    _LangfuseCallbackHandler = None
    _langfuse_available = False
else:
    _langfuse_available = True


# === 日志 ===
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent-web")


# === Agent 按 mode 缓存（agent / plan 各一个单例） ===
# uvicorn 在单 event loop 内并发多请求，首请求初始化期间若无锁，
# 并发的第二个请求会重复进入初始化分支。用 asyncio.Lock 保护。
_agent_by_mode: dict[str, object] = {}
_agent_init_error: str | None = None
_agent_init_lock = asyncio.Lock()


def _normalize_mode(mode: str | None) -> AgentMode:
    m = (mode or AGENT_MODE_DEFAULT or "agent").strip().lower()
    return "plan" if m == "plan" else "agent"


async def get_agent(mode: str | None = None) -> object:
    """懒加载 + 按 mode 单例。初始化失败时持久化错误状态，避免每次请求都重试。"""
    global _agent_init_error
    resolved = _normalize_mode(mode)

    if _agent_init_error is not None:
        raise RuntimeError(f"Agent initialization failed: {_agent_init_error}")

    cached = _agent_by_mode.get(resolved)
    if cached is not None:
        return cached

    async with _agent_init_lock:
        if _agent_init_error is not None:
            raise RuntimeError(f"Agent initialization failed: {_agent_init_error}")
        cached = _agent_by_mode.get(resolved)
        if cached is not None:
            return cached

        try:
            # plan 模式无 HITL（写/execute 由 Hooks deny）；agent 模式跟随 HITL_ENABLED
            hitl = bool(HITL_ENABLED) if resolved == "agent" else False
            agent = build_agent(hitl=hitl, mode=resolved, entrypoint="web")
            _agent_by_mode[resolved] = agent
            logger.info(
                "Agent initialized (mode=%s hitl=%s schemaVersion=%s)",
                resolved,
                hitl,
                SCHEMA_VERSION,
            )
        except Exception as e:
            error_msg = str(e)
            _agent_init_error = error_msg
            logger.error("Agent initialization failed, error persisted: %s", error_msg)
            raise RuntimeError(f"Agent initialization failed: {error_msg}") from e

    return _agent_by_mode[resolved]


# === FastAPI 应用 ===
@asynccontextmanager
async def lifespan(_app: FastAPI):
    yield
    await close_providers()


app = FastAPI(title="Agent Web Bridge", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


def is_loopback_host(host: str) -> bool:
    h = (host or "").strip().lower().split("%", 1)[0]
    return h in ("127.0.0.1", "localhost", "::1")


def check_bearer_auth(authorization: str | None, expected_token: str) -> bool:
    """校验 Authorization: Bearer <token>。expected_token 为空时视为不强制鉴权。"""
    token = (expected_token or "").strip()
    if not token:
        return True
    auth = (authorization or "").strip()
    return auth == f"Bearer {token}"


@app.middleware("http")
async def bearer_auth_middleware(request: Request, call_next):
    """保护对话、上传与静态产物；/health 放行。"""
    path = request.url.path
    if path == "/health" or path == "/docs" or path == "/openapi.json" or path == "/redoc":
        return await call_next(request)
    protected = (
        path.startswith("/chat")
        or path.startswith("/uploads")
        or path.startswith("/output")
        or path == "/upload"
    )
    # 运行时读 env，便于测试 monkeypatch 与热更新
    expected = os.getenv("AGENT_API_TOKEN", AGENT_API_TOKEN).strip()
    if protected and not check_bearer_auth(
        request.headers.get("Authorization"), expected
    ):
        return JSONResponse(status_code=401, content={"message": "Unauthorized"})
    return await call_next(request)


# === 静态文件目录（uploads 和 output 产物） ===
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOADS_DIR)), name="uploads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


# === Request / Response 模型 ===
class Attachment(BaseModel):
    id: str
    name: str
    mime: str
    size: int = 0
    remoteUrl: str = Field(default="", description="后端可访问的 URL，如 /uploads/xxx.png")


class ChatRequest(BaseModel):
    sessionId: str = Field(..., description="前端 session id，作为 langgraph thread_id")
    message: str = ""
    attachments: list[Attachment] = []
    mode: str = Field(
        default="",
        description='agent | plan；空则用服务端 AGENT_MODE 默认值',
    )


class ResumeRequest(BaseModel):
    sessionId: str
    mode: str = Field(
        default="",
        description='agent | plan；空则用服务端 AGENT_MODE 默认值',
    )
    # 每个 interrupt 一组决定，与 interrupt 事件的 groups 一一对应。
    # LangGraph 多 interrupt 恢复必须按 interrupt_id 索引：
    # https://docs.langchain.com/oss/python/langgraph/add-human-in-the-loop#resume-multiple-interrupts-with-one-invocation
    # tool_approval: {interruptId, kind?, decisions: [{type}]}
    # ask_user_question: {interruptId, kind, answers: [{questionId, selected, text}]}
    decisions: list[dict] = Field(
        ...,
        description=(
            '[{"interruptId": "...", "kind": "tool_approval"|"ask_user_question", '
            '"decisions": [{"type": "approve"|"reject"}], '
            '"answers": [{"questionId": "...", "selected": [...], "text": "..."}]}]'
        ),
    )












# === 附件处理 ===


def _get_local_path(remote_url: str) -> str:
    """将 /uploads/xxx.pdf 转换为相对路径 uploads/xxx.pdf。"""
    return remote_url.lstrip("/") if remote_url.startswith("/") else remote_url


def _build_doc_attachment_context(docs: list[Attachment]) -> str:
    """文档附件：路径 + mineru 解析提示（与是否 vision 无关）。"""
    if not docs:
        return ""
    lines = [
        "",
        "以下文档文件已上传到本地，你可以使用 mineru skill 解析这些文档：",
        "",
    ]
    for doc in docs:
        size_kb = doc.size / 1024 if doc.size else 0
        local_path = _get_local_path(doc.remoteUrl)
        lines.append(f"- 📄 **{doc.name}**（{doc.mime}, {size_kb:.1f} KB）：`{local_path}`")
    lines.extend(
        [
            "",
            "解析文档的方法：使用 execute 工具运行 mineru skill 的 extract.py 脚本。",
            "示例命令：",
            "```",
            f"python skills/mineru/scripts/extract.py {_get_local_path(docs[0].remoteUrl)} -o output/parsed.md",
            "```",
            "解析完成后，读取 output/parsed.md 即可获取文档内容，再据此回答用户问题。",
            "如果用户的消息为空或仅要求解析/总结文档，请先执行解析，再根据解析结果作答。",
        ]
    )
    return "\n".join(lines)


def _build_attachment_context(attachments: list[Attachment]) -> str:
    """非 vision 模式：图片仅给路径提示；文档给 mineru 提示。"""
    if not attachments:
        return ""

    images = [a for a in attachments if a.mime.startswith("image/")]
    docs = [a for a in attachments if not a.mime.startswith("image/")]

    lines = ["\n\n---", "## 用户上传的附件"]

    if images:
        lines.append("")
        lines.append(
            f"用户上传了 {len(images)} 张图片（当前模型不支持图片视觉识别，无法直接查看图片内容）："
        )
        lines.append("")
        for img in images:
            size_kb = img.size / 1024 if img.size else 0
            local_path = _get_local_path(img.remoteUrl)
            lines.append(
                f"- 🖼️ **{img.name}**（{img.mime}, {size_kb:.1f} KB）：`{local_path}`"
            )
        lines.append("")
        lines.append(
            "提示：如果用户要求识别图片内容，请告知当前模型不支持图片视觉理解，"
            "建议用户描述图片内容，或切换 LLM_PROVIDER=siliconflow / 设置 LLM_SUPPORTS_VISION=true。"
        )

    doc_block = _build_doc_attachment_context(docs)
    if doc_block:
        if images:
            lines.append("")
        lines.append(doc_block.lstrip("\n"))

    return "\n".join(lines)


def _build_chat_user_content(
    message: str,
    attachments: list[Attachment],
) -> str | list[dict]:
    """按当前 LLM vision 能力组装 user content（多模态或纯文本）。"""
    from agent_core.config import WORKSPACE_ROOT
    from agent_core.llm import llm_supports_vision
    from agent_core.multimodal import to_image_part

    images = [a for a in attachments if a.mime.startswith("image/")]
    docs = [a for a in attachments if not a.mime.startswith("image/")]
    doc_ctx = _build_doc_attachment_context(docs)
    text = (message or "") + (f"\n\n---\n## 用户上传的附件\n{doc_ctx}" if doc_ctx else "")

    if not images:
        if not attachments:
            return message
        # 仅文档：走原文本上下文（含 mineru 提示）
        return message + _build_attachment_context(attachments) if docs else message

    if not llm_supports_vision():
        return message + _build_attachment_context(attachments)

    # vision：图片进 image_url；仍附路径说明便于 agent 写文件工具
    path_notes = []
    for img in images:
        local_path = _get_local_path(img.remoteUrl)
        path_notes.append(f"- `{local_path}`（{img.name}, {img.mime}）")
    vision_text = text or "(见附图)"
    vision_text += (
        "\n\n---\n## 用户上传的图片（已作为视觉输入，路径如下供文件操作使用）\n"
        + "\n".join(path_notes)
    )

    parts: list[dict] = []
    for img in images:
        local_path = _get_local_path(img.remoteUrl)
        abs_path = WORKSPACE_ROOT / local_path
        try:
            parts.append(to_image_part(abs_path, mime=img.mime or None))
        except (OSError, ValueError, FileNotFoundError):
            # 单张失败时降级为路径提示，不阻断整轮
            vision_text += f"\n\n（无法加载图片字节: `{local_path}`，请用 view_image 重试）"
    parts.append({"type": "text", "text": vision_text})
    if len(parts) == 1:
        # 全部图片加载失败 → 退回文本模式
        return message + _build_attachment_context(attachments)
    return parts


class CancelRequest(BaseModel):
    sessionId: str
    runId: str | None = None


# === SSE 工具 ===
class StreamEmitter:

    def __init__(self, *, thread_id: str, run_id: str, message_id: str):
        self.thread_id = thread_id
        self.run_id = run_id
        self.message_id = message_id
        self.seq = 0

    def emit(self, payload: dict) -> dict:
        self.seq += 1
        event_type = payload.get("type", "")
        fields = {k: v for k, v in payload.items() if k != "type"}
        fields.setdefault("messageId", self.message_id)
        body = make_event(
            event_type,
            run_id=self.run_id,
            seq=self.seq,
            **fields,
        )
        event_id = str(body.get("eventId") or make_event_id(self.run_id, self.seq))
        return {
            "id": event_id,
            "event": "message",
            "data": json.dumps(body, ensure_ascii=False),
        }


def _sse(payload: dict, emitter: StreamEmitter | None = None) -> dict:
    """把业务事件 dict 包成 sse-starlette 帧。有 emitter 时走 run 协议。"""
    if emitter is not None:
        return emitter.emit(payload)
    event_type = payload.get("type", "")
    if event_type in ("start", "done") and "schemaVersion" not in payload:
        payload = make_event(event_type, **{k: v for k, v in payload.items() if k != "type"})
    return {"event": "message", "data": json.dumps(payload, ensure_ascii=False)}


def _open_langfuse_trace(session_id: str, run_name: str, *, run_id: str | None = None):
    """为本次请求开一个 langfuse 根 trace，返回 (config, trace_context_or_None)。

    关键点：langfuse v4 的 CallbackHandler 默认会把每个 langchain/langgraph 顶层
    chain 都当成独立 trace，于是 HumanInTheLoop/Resume/Tools 都飘在外面成一棵棵
    独立 trace，看起来像「跟踪断开」。修复方法：先用 client.start_as_current_observation
    显式建一个根 trace，再把 CallbackHandler 用 trace_context 锚到这个根上，
    所有子事件就都挂到这根 trace 下了。

    返回的 (cfg, trace_ctx) 配合使用：
      cfg  → 传给 astream()
      trace_ctx → 配合 client.start_as_current_observation(**trace_ctx) 作为
                  context manager 包住整个 stream，stream 结束自动 end 根。
    """
    cfg: dict = {
        "configurable": {"thread_id": session_id},
        "run_name": run_name,
        "recursion_limit": AGENT_RECURSION_LIMIT,
        # 同一会话的多次请求（含 HITL resume）通过 langfuse_session_id 归并到
        # langfuse UI 的同一个 session 视图。
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": ["deepagents", "web"],
            "run_id": run_id or "",
        },
    }
    if not _langfuse_available:
        return cfg, None

    from langfuse import get_client

    client = get_client()
    # 先用 start_observation 拿一个真实 trace_id（必须是 langfuse 自己的 hex，
    # 不能随机造）。CallbackHandler 拿到这个 trace_id 后会把所有根/子 run
    # 都挂到它下面（见 CallbackHandler._take_root_trace_context 源码），
    # 这就解决了 HumanInTheLoop/Resume/Tools 等子图 run 各自飘出顶层 trace
    # 的问题。
    obs = client.start_observation(
        name=run_name,
        as_type="span",
        metadata={
            "session_id": session_id,
            "tags": ["deepagents", "web"],
            "run_id": run_id or "",
        },
    )
    trace_id = obs.trace_id
    # 立刻 end 这个空根：真正的事件由 CallbackHandler 透过 trace_context 挂进来
    # —— handler 会用同名 trace_id 在事件到达时建/接管这个 trace 的 span 树。
    obs.end()
    cfg["callbacks"] = [_LangfuseCallbackHandler(trace_context={"trace_id": trace_id})]
    return cfg, trace_id


def _build_config(session_id: str, run_name: str) -> dict:
    """兼容旧调用方：只构造 config，不开 langfuse 根 trace。

    根 trace 由 _stream_with_artifacts 入口的 _open_langfuse_trace 统一开，
    保证整次 SSE 流（含 aget_state / artifact 检测）都在同一根 trace 下。
    """
    return {
        "configurable": {"thread_id": session_id},
        "run_name": run_name,
        "recursion_limit": AGENT_RECURSION_LIMIT,
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": ["deepagents", "web"],
        },
    }


def _accumulate_tool_call_chunks(msg_chunk, target: dict) -> None:
    """把 AIMessageChunk 的 tool_call_chunks 累积到 target dict（按 index 聚合）。

    父图与子 agent 各自维护一份 target，互不污染。
    """
    tool_call_chunks = getattr(msg_chunk, "tool_call_chunks", None) or []
    for tc in tool_call_chunks:
        idx = tc.get("index", 0)
        if idx not in target:
            target[idx] = {"id": "", "name": "", "args": ""}
        if tc.get("id"):
            target[idx]["id"] = tc["id"]
        if tc.get("name"):
            target[idx]["name"] += tc["name"]
        if tc.get("args"):
            target[idx]["args"] += tc["args"]


def _claim_pending_task(pending_task_calls: list[dict]) -> tuple[str, str, str]:
    """从待认领的 task() 调用中取第一个未认领项，解析 description/subagent_type。

    Returns: (description, subagent_type, call_id)。找不到时返回兜底值。
    """
    for item in pending_task_calls:
        if not item.get("claimed"):
            item["claimed"] = True
            args_raw = item.get("args", "")
            description = "子智能体任务"
            subagent_type = "subagent"
            try:
                if isinstance(args_raw, str) and args_raw:
                    parsed = json.loads(args_raw)
                    if isinstance(parsed, dict):
                        description = str(parsed.get("description") or description)
                        subagent_type = str(parsed.get("subagent_type") or subagent_type)
                elif isinstance(args_raw, dict):
                    description = str(args_raw.get("description") or description)
                    subagent_type = str(args_raw.get("subagent_type") or subagent_type)
            except (json.JSONDecodeError, ValueError):
                pass
            return description, subagent_type, item.get("id", "")
    return "子智能体任务", "subagent", ""


async def _emit_subagent_tool_events(
    msg_chunk,
    pending_tools: dict,
    subagent_id: str,
    emitter: StreamEmitter | None = None,
) -> AsyncGenerator[dict, None]:
    """把子 agent 内部的 ToolMessage 转成带 subagentId 的 tool_call/tool_result 事件。

    复用 pending_tools（子 agent 自有累积）匹配 args；匹配不到则 args 留空。
    """
    name = msg_chunk.name or ""
    tool_call_id = getattr(msg_chunk, "tool_call_id", "") or ""

    pending = None
    if tool_call_id:
        for tc in pending_tools.values():
            if tc.get("id") == tool_call_id:
                pending = tc
                break
    if pending is None:
        for tc in pending_tools.values():
            if tc.get("name") == name:
                pending = tc
                break

    call_id = (
        (pending.get("id") if pending else "")
        or tool_call_id
        or f"tc_{uuid.uuid4().hex[:8]}"
    )
    args_value = pending.get("args", "") if pending else ""
    _out = str(msg_chunk.content)
    _limit = 5000 if name in (
        "web_search", "web_fetch",
    ) else 500
    output = _out[:_limit]

    yield _sse({
        "type": "tool_call",
        "callId": call_id,
        "name": pending.get("name", name) if pending else name,
        "args": args_value,
        "subagentId": subagent_id,
    }, emitter)
    yield _sse({
        "type": "tool_result",
        "callId": call_id,
        "name": name,
        "output": output,
        "subagentId": subagent_id,
    }, emitter)
    pending_tools.clear()


async def _stream_agent(
    agent_obj,
    input_payload: dict,
    config: dict,
    message_id: str,
    *,
    emitter: StreamEmitter | None = None,
    http_request: Request | None = None,
    thread_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """通用流式生成器：处理 stream + HITL 检查 + 收尾事件。

    注意：
    1. 必须是 async def，否则返回的是普通生成器，
       sse_starlette 的 EventSourceResponse 会用 async for 遍历，
       'async for' over sync generator 会报 TypeError。
    2. 必须用 astream() 而不是 stream()，否则同步迭代会阻塞 asyncio 事件循环，
       sse_starlette 无法及时 flush 数据到 socket。
    """
    registry = get_run_registry()
    tid = thread_id or str(
        (config.get("configurable") or {}).get("thread_id") or ""
    )

    def _stopped() -> bool:
        if tid and registry.should_stop(tid):
            return True
        return False

    started_at = time.time()
    try:
        yield _sse({"type": "start", "messageId": message_id}, emitter)

        # 工具调用分片累积（与 entrypoints/cli.py 的 log_tool_call 一致）
        # pending_tool_calls 记录从 AIMessageChunk.tool_call_chunks 里拼出来的工具调用
        # —— 这些是"模型决定调工具"的元数据，进入思考区（独立于最终答案）。
        pending_tool_calls: dict[int, dict] = {}
        # 子智能体跟踪（subgraphs=True 时启用）：
        #   active_subagents: key=base namespace 'tools:<tid>'（即 subagentId），value=子 agent 元信息
        #   pending_task_calls: 待认领的 task() 工具调用，子 agent 首个 chunk 到达时从中取 description/subagent_type
        active_subagents: dict[str, dict] = {}
        pending_task_calls: list[dict] = []  # 每项 = {"id": call_id, "args": "...", "claimed": False}
        task_indices_seen: set[int] = set()  # 已入 pending_task_calls 的 pending idx，避免重复
        event_count = 0

        # === 思考 vs 最终答案：基于消息结构判断，不依赖模型输出文本标记 ===
        # ReAct agent 的消息序列：
        #   AIMessageChunk(有 tool_call_chunks)  → 工具调用轮（过渡语）
        #   ToolMessage                          → 工具返回
        #   AIMessageChunk(无 tool_call_chunks)  → 最终答案轮
        # 路由规则：
        #   - reasoning_content          → thinking_delta（始终）
        #   - content + 有 tool_call_chunks → thinking_delta（工具调用轮的过渡语）
        #   - content + 无 tool_call_chunks → delta（最终答案）
        seen_tool_message = False       # 是否已经见过 ToolMessage
        current_ai_has_tool_calls = False  # 当前 AIMessage 轮是否出现过 tool_call_chunks
        # 跟踪上一个父图 AIMessage 的 id，用于检测轮次边界。
        # langgraph stream_mode="messages" 下，同一 AIMessage 的流式 chunk 共享同一 id，
        # 新轮次 AIMessage 的 id 不同。当 id 变化时重置 current_ai_has_tool_calls，
        # 防御"工具异常/HITL 中断无 ToolMessage 导致标志卡住 True"的边角场景
        # （标准 ReAct 下工具异常会生成 ToolMessage 正常重置，此处为防御性兜底）。
        _last_ai_msg_id = None

        # 优先用 astream（真异步），没有就回退到在 thread 里跑 stream()
        # subgraphs=True：让子智能体（task() spawn 的子图）内部消息回流父 stream，
        # 产出形状从 (chunk, _meta) 变为 (namespace_tuple, (chunk, _meta))。
        # 父图自身 chunk 的 namespace=()；子智能体内部 chunk 的 namespace=('tools:<tid>',)。
        astream_fn = getattr(agent_obj, "astream", None)
        if astream_fn is not None:
            stream_iter = astream_fn(
                input_payload, config=config, stream_mode="messages", subgraphs=True
            )
        else:
            loop = asyncio.get_running_loop()

            def _gen():
                yield from agent_obj.stream(
                    input_payload, config=config, stream_mode="messages", subgraphs=True
                )

            stream_iter = _aiter_from_sync(loop, _gen())

        async for stream_item in stream_iter:
            if _stopped():
                yield _sse({
                    "type": "error",
                    "message": "RunCancelled: cancelled by client or deadline",
                }, emitter)
                yield _sse({"type": "done", "messageId": message_id}, emitter)
                return
            if http_request is not None:
                try:
                    if await http_request.is_disconnected():
                        await registry.cancel(tid)
                        yield _sse({
                            "type": "error",
                            "message": "RunCancelled: client disconnected",
                        }, emitter)
                        yield _sse({"type": "done", "messageId": message_id}, emitter)
                        return
                except Exception:  # noqa: BLE001
                    pass
            # subgraphs=True 单 stream_mode 形状：(namespace_tuple, (chunk, _meta))
            # 防御性兜底：若某后端版本未按预期产出，降级为 namespace=()。
            if (
                isinstance(stream_item, tuple)
                and len(stream_item) == 2
                and isinstance(stream_item[0], tuple)
                and isinstance(stream_item[1], tuple)
            ):
                namespace, (msg_chunk, _meta) = stream_item
            else:
                namespace = ()
                msg_chunk, _meta = stream_item  # type: ignore[misc]
            event_count += 1
            # 子智能体识别：namespace 非空 = 来自子图（task() spawn 的子 agent）
            is_subagent = isinstance(namespace, tuple) and len(namespace) > 0
            logger.debug(
                "stream chunk #%d ns=%s is_sub=%s type=%s content=%r reasoning=%r tool_call_chunks=%s ai_has_tc=%s seen_tm=%s ckpt_ns=%s",
                event_count,
                namespace if is_subagent else "()",
                is_subagent,
                type(msg_chunk).__name__,
                str(getattr(msg_chunk, "content", ""))[:80],
                str(getattr(msg_chunk, "additional_kwargs", {}).get("reasoning_content", ""))[:80],
                repr(getattr(msg_chunk, "tool_call_chunks", None) or [])[:200],
                current_ai_has_tool_calls,
                seen_tool_message,
                str(_meta.get("langgraph_checkpoint_ns", "")) if isinstance(_meta, dict) else "",
            )

            # === 子智能体内部 chunk 处理 ===
            # 子 agent 的 AIMessageChunk（含其内部工具调用的 tool_call_chunks）累积到
            # 该子 agent 自有的 pending 字典；ToolMessage 作为嵌套步骤发射。
            # 不流式子 agent 的思考文字（符合"任务+内嵌步骤"粒度）。
            if is_subagent:
                subagent_id = namespace[0]
                # 首次见到该子 agent：发 subagent_start，从 pending_task_calls 取 description
                if subagent_id not in active_subagents:
                    description, subagent_type, call_id = _claim_pending_task(
                        pending_task_calls
                    )
                    active_subagents[subagent_id] = {
                        "call_id": call_id,
                        "subagent_type": subagent_type,
                        "description": description,
                        "pending_tools": {},  # 子 agent 自有的工具调用分片累积
                    }
                    yield _sse({
                        "type": "subagent_start",
                        "subagentId": subagent_id,
                        "subagentType": subagent_type,
                        "description": description,
                    }, emitter)
                sub_state = active_subagents[subagent_id]
                if isinstance(msg_chunk, ToolMessage):
                    # 子 agent 内部工具返回 = 嵌套步骤
                    async for evt in _emit_subagent_tool_events(
                        msg_chunk, sub_state["pending_tools"], subagent_id, emitter
                    ):
                        yield evt
                elif isinstance(msg_chunk, AIMessageChunk):
                    # 累积子 agent 内部工具调用分片（用于 ToolMessage 时取 args）
                    _accumulate_tool_call_chunks(msg_chunk, sub_state["pending_tools"])
                # 子 agent chunk 一律不进入下方父图分支
                continue

            if isinstance(msg_chunk, AIMessageChunk):
                # 轮次边界检测：基于 AIMessage id 检测新轮次。
                # 同一 AIMessage 的流式 chunk 共享同一 id；新轮次 AIMessage 的 id 不同。
                # 当 id 变化时重置 current_ai_has_tool_calls，防御工具异常/HITL 中断
                # 无 ToolMessage 导致标志卡住 True、后续轮 content 误走 thinking_delta。
                # 防御性：id 为空（某些模型/配置不设 id）时不触发重置，保守不误判。
                _this_msg_id = getattr(msg_chunk, "id", None)
                if _this_msg_id and _last_ai_msg_id is not None and _this_msg_id != _last_ai_msg_id:
                    current_ai_has_tool_calls = False
                if _this_msg_id:
                    _last_ai_msg_id = _this_msg_id

                content = msg_chunk.content
                # 兼容 content 是 list（多模态片段）的情况
                if isinstance(content, list):
                    text_parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    ]
                    reasoning_parts = [
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") in ("thinking", "reasoning")
                    ]
                    content = "".join(text_parts)
                    reasoning_content = "".join(reasoning_parts)
                else:
                    reasoning_content = ""

                # 从 additional_kwargs 中提取 reasoning_content（OpenAI 兼容格式）
                if not reasoning_content:
                    reasoning_content = msg_chunk.additional_kwargs.get("reasoning_content", "") or ""

                if reasoning_content:
                    yield _sse({"type": "thinking_delta", "delta": reasoning_content}, emitter)
                if content:
                    # 基于消息结构路由（不依赖模型输出文本标记）：
                    # - 当前 AIMessage 轮有 tool_call_chunks → 工具调用轮的过渡语 → thinking
                    # - 无 tool_call_chunks → 最终答案 → delta
                    if current_ai_has_tool_calls:
                        yield _sse({"type": "thinking_delta", "delta": content}, emitter)
                    else:
                        yield _sse({"type": "delta", "delta": content}, emitter)
                    # 没文本但有 chunk（如纯工具调用）→ 给前端一个思考指示
            elif isinstance(msg_chunk, ToolMessage):
                # 工具执行完成：拆成两个事件 —— 思考区独立渲染
                #   1) tool_call   : "模型决定调工具"（name + args）
                #   2) tool_result : "工具执行返回"   （output）
                seen_tool_message = True
                # 工具返回后，下一轮 AIMessage 是新的轮次 → 重置
                current_ai_has_tool_calls = False
                name = msg_chunk.name or ""
                tool_call_id = getattr(msg_chunk, "tool_call_id", "") or ""

                # === task() 工具返回检测 ===
                # 父图 "tools" 节点处理 task() 时，_meta["langgraph_checkpoint_ns"]
                # 形如 'tools:<tid>'（无 '|'），与该次 task() spawn 的子 agent 共享 tid。
                # 若该 ns 命中 active_subagents，说明这是 task() 结束 → 发 subagent_done，
                # 不再发 tool_call/tool_result（避免 task() 重复出现在思考区）。
                ckpt_ns = ""
                if isinstance(_meta, dict):
                    ckpt_ns = _meta.get("langgraph_checkpoint_ns", "") or ""
                if ckpt_ns and ckpt_ns in active_subagents:
                    yield _sse({"type": "subagent_done", "subagentId": ckpt_ns}, emitter)
                    del active_subagents[ckpt_ns]
                    pending_tool_calls.clear()
                    continue
                # 边界情况：子 agent 未产生内部 chunk（无 active 记录），但 pending 命中 task
                # → 补发 subagent_start + subagent_done，保持前端卡片完整。
                if name == "task":
                    description, subagent_type, _call_id = _claim_pending_task(
                        pending_task_calls
                    )
                    fallback_id = ckpt_ns or f"sub_{uuid.uuid4().hex[:8]}"
                    yield _sse({
                        "type": "subagent_start",
                        "subagentId": fallback_id,
                        "subagentType": subagent_type,
                        "description": description,
                    }, emitter)
                    yield _sse({"type": "subagent_done", "subagentId": fallback_id}, emitter)
                    pending_tool_calls.clear()
                    continue

                # 找对应的 pending tool call（按 id 优先，按 name 兜底）
                pending = None
                if tool_call_id:
                    for tc in pending_tool_calls.values():
                        if tc.get("id") == tool_call_id:
                            pending = tc
                            break
                if pending is None:
                    for tc in pending_tool_calls.values():
                        if tc.get("name") == name:
                            pending = tc
                            break

                if pending is not None:
                    # 取一个稳定的 callId：优先用 pending 里的 id / ToolMessage 的 id / 生成新 id
                    call_id = (
                        pending.get("id")
                        or tool_call_id
                        or f"tc_{uuid.uuid4().hex[:8]}"
                    )
                    # 1) 先发 tool_call：进入 message.toolCalls，状态 running
                    yield _sse({
                        "type": "tool_call",
                        "callId": call_id,
                        "name": pending.get("name", name),
                        "args": pending.get("args", ""),
                    }, emitter)
                    # 2) 再发 tool_result：补全同 callId 的 output / status=completed
                    _output_str = str(msg_chunk.content)
                    _out_limit = 5000 if name in (
                        "web_search", "web_fetch",
                    ) else 500
                    yield _sse({
                        "type": "tool_result",
                        "callId": call_id,
                        "name": name,
                        "output": _output_str[:_out_limit],
                    }, emitter)
                else:
                    # pending 找不到（tool_call_chunks 未累积到 name），
                    # 不再降级发旧 tool 事件（会污染 content），统一发 tool_call + tool_result
                    call_id = tool_call_id or f"tc_{uuid.uuid4().hex[:8]}"
                    yield _sse({
                        "type": "tool_call",
                        "callId": call_id,
                        "name": name,
                        "args": "",
                    }, emitter)
                    _output_str = str(msg_chunk.content)
                    _out_limit = 5000 if name in (
                        "web_search", "web_fetch",
                    ) else 500
                    yield _sse({
                        "type": "tool_result",
                        "callId": call_id,
                        "name": name,
                        "output": _output_str[:_out_limit],
                    }, emitter)

                pending_tool_calls.clear()

            # 累积 AIMessageChunk 的工具调用分片
            tool_call_chunks = getattr(msg_chunk, "tool_call_chunks", None) or []
            # 只有包含实际工具调用（name 或 id 非空）的 chunk 才标记为工具调用轮。
            # 某些模型/解析器会返回空壳 tool_call_chunks（name/id 均为 None 的占位），
            # 若不过滤，current_ai_has_tool_calls 会被误置 True 且普通问题无 ToolMessage
            # 来重置，导致 content 全部走 thinking_delta，最终答案区为空（"不回复"）。
            has_real_tool_call = any(
                isinstance(tc, dict) and (tc.get("name") or tc.get("id"))
                for tc in tool_call_chunks
            )
            if has_real_tool_call:
                current_ai_has_tool_calls = True
            _accumulate_tool_call_chunks(msg_chunk, pending_tool_calls)
            # 注册 task() 调用到 pending_task_calls（供子 agent 首个 chunk 认领取 description）
            for idx, tc in pending_tool_calls.items():
                if idx in task_indices_seen:
                    continue
                if tc.get("name") == "task":
                    pending_task_calls.append({
                        "id": tc.get("id", ""),
                        "args": tc.get("args", ""),
                        "claimed": False,
                    })
                    task_indices_seen.add(idx)

        # 检查 HITL / ask_user_question 中断
        # 必须用 aget_state（异步）：get_state 是同步阻塞调用，
        # 在 async 上下文里会卡住事件循环，导致 SSE 数据无法 flush。
        state = await agent_obj.aget_state(config)
        if state.next:
            from tools.ask_user_question import collect_interrupt_groups

            groups = collect_interrupt_groups(state)
            if groups:
                yield _sse({"type": "interrupt", "groups": groups}, emitter)

        logger.info(
            "stream done messageId=%s events=%d duration=%.2fs",
            message_id,
            event_count,
            time.time() - started_at,
        )
        yield _sse({"type": "done", "messageId": message_id}, emitter)
    except asyncio.CancelledError:
        yield _sse({
            "type": "error",
            "message": "RunCancelled: cancelled",
        }, emitter)
        yield _sse({"type": "done", "messageId": message_id}, emitter)
        raise
    except Exception as e:  # noqa: BLE001
        from agent_core.llm_errors import format_llm_stream_error

        logger.exception("Stream error")
        yield _sse(
            {"type": "error", "message": format_llm_stream_error(e)},
            emitter,
        )
        yield _sse({"type": "done", "messageId": message_id}, emitter)


async def _stream_with_artifacts(
    agent_obj,
    input_payload,
    config: dict,
    message_id: str,
    *,
    emitter: StreamEmitter | None = None,
    http_request: Request | None = None,
    thread_id: str | None = None,
    run_id: str | None = None,
) -> AsyncGenerator[dict, None]:
    """流式输出 + 产物检测的公共包装。

    /chat 和 /chat/resume 的 event_stream 逻辑几乎完全相同：
    snapshot output/ → 透传 stream 事件 → 拦截 done 末尾插入 artifact → 放行 done。
    抽到这里避免两处闭包重复维护。

    行为：
    - 透传所有事件；error 事件透传后立即终止；
    - done 事件暂存到最后，先发 output/ 下新增的 artifact 事件，再发 done；
    - 若 stream 抛异常，_stream_agent 内部已转成 error+done，这里照常透传。
    """
    snapshot_before = snapshot_output_dir()
    done_evt = None
    async for evt in _stream_agent(
        agent_obj,
        input_payload,
        config,
        message_id,
        emitter=emitter,
        http_request=http_request,
        thread_id=thread_id,
    ):
        evt_data = evt.get("data", "")
        try:
            parsed = json.loads(evt_data)
            if parsed.get("type") == "done":
                done_evt = evt
                continue
            if parsed.get("type") == "error":
                yield evt
                return
        except (json.JSONDecodeError, TypeError):
            pass
        yield evt
    if done_evt is not None:
        new_artifacts = detect_new_artifacts(snapshot_before)
        for art in new_artifacts:
            payload = {"type": "artifact", **art}
            if run_id:
                payload["runId"] = run_id
            yield _sse(payload, emitter)
        if new_artifacts:
            logger.info("Detected %d new artifact(s) in output/", len(new_artifacts))
        # 显式 flush langfuse，避免 done 已经推给前端、langfuse trace 还在本地
        # 排队导致 UI 上「跟踪断开」的感觉。
        if _langfuse_available:
            try:
                from langfuse import get_client

                get_client().flush()
            except Exception:
                logger.debug("langfuse flush failed", exc_info=True)
        yield done_evt


def _checkpoint_id_from_state(state: Any) -> str | None:
    cfg = getattr(state, "config", None) or {}
    if isinstance(cfg, dict):
        conf = cfg.get("configurable") or {}
        if isinstance(conf, dict):
            cid = conf.get("checkpoint_id")
            if cid:
                return str(cid)
    return None


async def _run_event_stream(
    *,
    agent_obj,
    input_payload,
    session_id: str,
    run_name: str,
    http_request: Request,
) -> AsyncGenerator[dict, None]:
    """统一 chat/resume：获取锁 → emitter → stream → 释放。"""
    registry = get_run_registry()
    try:
        active = await registry.try_begin(
            session_id,
            deadline_seconds=AGENT_RUN_DEADLINE_SECONDS,
        )
    except RunConflictError as e:
        yield {
            "event": "message",
            "data": json.dumps(
                {
                    "type": "error",
                    "message": f"RunConflict: {e}",
                    "activeRunId": e.active_run_id,
                },
                ensure_ascii=False,
            ),
        }
        return

    message_id = str(uuid.uuid4())
    emitter = StreamEmitter(
        thread_id=session_id, run_id=active.run_id, message_id=message_id
    )
    config, _trace_id = _open_langfuse_trace(
        session_id, run_name, run_id=active.run_id
    )
    try:
        async for evt in _stream_with_artifacts(
            agent_obj,
            input_payload,
            config,
            message_id,
            emitter=emitter,
            http_request=http_request,
            thread_id=session_id,
            run_id=active.run_id,
        ):
            yield evt
    finally:
        await registry.end(session_id, active.run_id)


def _client_disconnect_handler(session_id: str):
    """Mark the session run cancelled when its SSE client disappears.

    EventSourceResponse cancels content iteration on disconnect.  Explicitly
    marking the registry entry prevents a cancelled iterator from leaving a
    non-cancelled active run that rejects every later chat/resume with 409.
    """
    async def handle_disconnect(_message: dict) -> None:
        await get_run_registry().cancel(session_id)

    return handle_disconnect

async def _aiter_from_sync(loop, sync_gen):
    """把同步生成器包成异步迭代器，在默认 executor 里跑。"""
    it = iter(sync_gen)
    while True:
        try:
            item = await loop.run_in_executor(None, next, it)
        except StopIteration:
            return
        yield item


# === 路由 ===
@app.get("/health")
async def health():
    return JSONResponse(
        {
            "ok": True,
            "ts": int(time.time() * 1000),
            "hitl_enabled": HITL_ENABLED,
            "agent_mode_default": AGENT_MODE_DEFAULT,
            "schema_version": SCHEMA_VERSION,
            "upload_dir": str(UPLOADS_DIR.resolve()),
        }
    )
























@app.post("/upload")
async def upload(file: UploadFile = File(...)):
    """保存上传文件到 workspace/uploads，返回可访问的 URL。"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="missing filename")
    ext = Path(file.filename).suffix.lower()
    allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".pdf",
                   ".txt", ".md", ".docx", ".doc", ".xlsx", ".xls", ".csv", ".json",
                   ".ppt", ".pptx"}
    if ext and ext not in allowed_ext:
        raise HTTPException(status_code=400, detail=f"unsupported file type: {ext}")
    safe_name = f"{uuid.uuid4().hex}{ext}"
    target = UPLOADS_DIR / safe_name
    content = await file.read()
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=413,
            detail=f"file too large: {len(content)} bytes exceeds limit of {MAX_UPLOAD_SIZE} bytes"
        )
    target.write_bytes(content)
    return {
        "url": f"/uploads/{safe_name}",
        "name": file.filename,
        "mime": file.content_type or mimetypes.guess_type(file.filename)[0] or "application/octet-stream",
        "size": target.stat().st_size,
    }


@app.post("/chat")
async def chat(req: ChatRequest, request: Request):
    user_content: str | list[dict] = _build_chat_user_content(req.message, req.attachments)
    mode = _normalize_mode(req.mode)

    try:
        agent_obj = await get_agent(mode)
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )

    registry = get_run_registry()
    existing = registry.get(req.sessionId)
    if existing is not None and not existing.cancelled:
        return JSONResponse(
            status_code=409,
            content={
                "message": "session already has an active run",
                "activeRunId": existing.run_id,
            },
        )

    logger.info(
        "chat session=%s mode=%s msg=%r attachments=%d",
        req.sessionId,
        mode,
        req.message[:40],
        len(req.attachments),
    )

    async def event_stream() -> AsyncGenerator[dict, None]:
        async for evt in _run_event_stream(
            agent_obj=agent_obj,
            input_payload={"messages": [{"role": "user", "content": user_content}]},
            session_id=req.sessionId,
            run_name=f"chat:{req.message[:20]}",
            http_request=request,
        ):
            yield evt

    return EventSourceResponse(
        event_stream(),
        ping=15,
        client_close_handler_callable=_client_disconnect_handler(req.sessionId),
    )


@app.post("/chat/resume")
async def resume(req: ResumeRequest, request: Request):
    """HITL 中断后提交用户决定，继续流式输出。"""
    mode = _normalize_mode(req.mode)
    try:
        agent_obj = await get_agent(mode)
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )

    registry = get_run_registry()
    existing = registry.get(req.sessionId)
    if existing is not None and not existing.cancelled:
        return JSONResponse(
            status_code=409,
            content={
                "message": "session already has an active run",
                "activeRunId": existing.run_id,
            },
        )

    # 先校验 resume，避免开启 run 后才发现无效
    from tools.ask_user_question import ResumeValidationError, validate_resume_against_state

    config_peek: dict = {"configurable": {"thread_id": req.sessionId}}
    state = await agent_obj.aget_state(config_peek)
    try:
        resume_map = validate_resume_against_state(state, req.decisions)
    except ResumeValidationError as e:
        return JSONResponse(
            status_code=e.status_code,
            content={"message": str(e)},
        )

    logger.info(
        "resume session=%s mode=%s decisions=%s",
        req.sessionId,
        mode,
        req.decisions,
    )

    async def event_stream() -> AsyncGenerator[dict, None]:
        async for evt in _run_event_stream(
            agent_obj=agent_obj,
            input_payload=Command(resume=resume_map),
            session_id=req.sessionId,
            run_name=f"resume:{req.sessionId[:8]}",
            http_request=request,
        ):
            yield evt

    return EventSourceResponse(
        event_stream(),
        ping=15,
        client_close_handler_callable=_client_disconnect_handler(req.sessionId),
    )


@app.post("/chat/cancel")
async def cancel_chat(req: CancelRequest):
    """取消活跃 run（前端 stop 时调用）。"""
    registry = get_run_registry()
    ok = await registry.cancel(req.sessionId, req.runId)
    return {
        "sessionId": req.sessionId,
        "cancelled": ok,
        "runId": req.runId or registry.active_run_id(req.sessionId),
    }




@app.get("/chat/state")
async def chat_state(sessionId: str):
    """读 thread 状态：是否有 pending interrupt、当前 todos、消息数。

    供前端启动时恢复 UI：换 SqliteSaver 后 thread 状态跨进程重启可恢复，
    但前端原先只在流式事件里收 todos / interrupt，重启前端后无法重新获取。
    前端在 session 加载时调本端点，发现 hasInterrupt 则恢复审批 UI，
    todos 则恢复待办列表。
    """
    try:
        agent_obj = await get_agent()
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )
    # 与 _stream_with_artifacts 一致，用 aget_state（异步）避免阻塞事件循环
    config: dict = {"configurable": {"thread_id": sessionId}}
    state = await agent_obj.aget_state(config)
    interrupts: list[dict] = []
    interrupt_groups: list[dict] = []
    if state.next:
        from tools.ask_user_question import collect_interrupt_groups

        interrupt_groups = collect_interrupt_groups(state)
        for g in interrupt_groups:
            if g.get("kind") == "tool_approval":
                interrupts.extend(g.get("toolCalls") or [])
    values = state.values or {}
    todos = values.get("todos", []) if isinstance(values, dict) else []
    messages = values.get("messages", []) if isinstance(values, dict) else []
    return {
        "sessionId": sessionId,
        # A cancelled/failed graph can retain a next node without a real interrupt.
        # Only actual interrupt groups should restore the approval UI.
        "hasInterrupt": bool(interrupt_groups),
        "interrupts": interrupts,
        "interruptGroups": interrupt_groups,
        "todos": todos,
        "messageCount": len(messages),
        "checkpointId": _checkpoint_id_from_state(state),
        "activeRunId": get_run_registry().active_run_id(sessionId),
    }


# === 历史消息恢复：从 SqliteSaver checkpoint 读出 langgraph 消息序列，
#    映射成前端 Message 格式（与 chat store 的累积语义一致）===
def _extract_text(content) -> str:
    """从多模态 content（可能是 str 或 list[dict]）里提取纯文本。"""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for p in content:
            if isinstance(p, dict) and p.get("type") == "text":
                parts.append(p.get("text", ""))
        return "".join(parts)
    return str(content)


def _msg_timestamp(msg, fallback_ms: int) -> int:
    """从 message 的 response_metadata 取时间戳（毫秒），取不到用 fallback。

    OpenAI 兼容模型在 response_metadata.created 放秒级 unix 时间戳。
    HumanMessage / ToolMessage 通常没有，统一兜底。
    """
    meta = getattr(msg, "response_metadata", {}) or {}
    created = meta.get("created")
    if created is None:
        # 部分模型嵌一层 response_metadata
        inner = meta.get("response_metadata", {}) if isinstance(meta, dict) else {}
        created = inner.get("created") if isinstance(inner, dict) else None
    if created:
        try:
            return int(created) * 1000
        except (TypeError, ValueError):
            pass
    return fallback_ms


def _map_history_messages(raw_messages: list, session_id: str) -> list[dict]:
    """把 langgraph 消息序列映射成前端 Message 列表。

    映射规则（与 chat store send() 的累积语义一致，保证刷新前后 UI 结构相同）：
    - SystemMessage → 跳过（系统提示不展示）
    - HumanMessage → 新建一条 user message
    - 一段 user message 后的连续 AIMessage + ToolMessage 合并成一条 assistant message：
        · content            = 最后一条无 tool_calls 的 AIMessage.content（最终答案）
        · thinkingContent    = 所有 AIMessage 的 reasoning_content + 工具调用轮 AIMessage 的过渡 content
        · toolCalls          = 所有 tool_calls 配对后续 ToolMessage 的 output
        · hasThought         = 有思考内容或工具调用时 True
    """
    now_ms = int(time.time() * 1000)
    out: list[dict] = []
    current_assistant: dict | None = None
    seq = 0  # 用于让 createdAt 单调递增

    def next_ts() -> int:
        nonlocal seq
        seq += 1
        # 往前推，保证前面的消息时间更早（now - N + seq）
        return now_ms - (len(raw_messages) - seq) * 1000

    def flush():
        nonlocal current_assistant
        if current_assistant is not None:
            if not current_assistant.get("thinkingContent"):
                current_assistant.pop("thinkingContent", None)
            if not current_assistant.get("toolCalls"):
                current_assistant.pop("toolCalls", None)
            out.append(current_assistant)
            current_assistant = None

    for msg in raw_messages:
        if isinstance(msg, SystemMessage):
            continue
        if isinstance(msg, HumanMessage):
            flush()
            out.append({
                "id": f"m_{uuid.uuid4().hex[:8]}",
                "sessionId": session_id,
                "role": "user",
                "content": _extract_text(msg.content),
                "status": "complete",
                "createdAt": _msg_timestamp(msg, next_ts()),
            })
        elif isinstance(msg, AIMessage):
            if current_assistant is None:
                current_assistant = {
                    "id": f"m_{uuid.uuid4().hex[:8]}",
                    "sessionId": session_id,
                    "role": "assistant",
                    "content": "",
                    "hasThought": False,
                    "status": "complete",
                    "createdAt": _msg_timestamp(msg, next_ts()),
                }
            content = _extract_text(msg.content)
            reasoning = msg.additional_kwargs.get("reasoning_content", "") or ""
            tool_calls = getattr(msg, "tool_calls", None) or []
            if tool_calls:
                # 工具调用轮：content 是过渡语 → thinking
                current_assistant["hasThought"] = True
                if content:
                    current_assistant["thinkingContent"] = (
                        current_assistant.get("thinkingContent", "") + content
                    )
                if reasoning:
                    current_assistant["thinkingContent"] = (
                        current_assistant.get("thinkingContent", "") + reasoning
                    )
                for tc in tool_calls:
                    tc_id = tc.get("id") or f"tc_{uuid.uuid4().hex[:8]}"
                    current_assistant.setdefault("toolCalls", []).append({
                        "id": tc_id,
                        "name": tc.get("name", ""),
                        "args": tc.get("args", ""),
                        "status": "running",
                    })
            else:
                # 最终答案轮
                if reasoning:
                    current_assistant["hasThought"] = True
                    current_assistant["thinkingContent"] = (
                        current_assistant.get("thinkingContent", "") + reasoning
                    )
                if content:
                    current_assistant["content"] += content
        elif isinstance(msg, ToolMessage):
            if current_assistant is None:
                continue
            tool_call_id = getattr(msg, "tool_call_id", "") or ""
            name = msg.name or ""
            _out = str(msg.content)
            _limit = 5000 if name in (
                "web_search", "web_fetch",
            ) else 500
            output = _out[:_limit]
            record = None
            for tc in current_assistant.get("toolCalls", []):
                if tc["id"] == tool_call_id:
                    record = tc
                    break
            if record is None:
                for tc in current_assistant.get("toolCalls", []):
                    if tc["name"] == name and tc["status"] == "running":
                        record = tc
                        break
            if record:
                record["output"] = output
                record["status"] = "completed"
            else:
                current_assistant.setdefault("toolCalls", []).append({
                    "id": tool_call_id or f"tc_{uuid.uuid4().hex[:8]}",
                    "name": name,
                    "args": "",
                    "output": output,
                    "status": "completed",
                })
    flush()
    return out


@app.get("/chat/sessions")
async def chat_sessions():
    """列出所有持久化的会话线程，返回前端 SessionSummary 格式。

    前端刷新后可从本端点恢复会话列表（而不仅依赖前端本地存储），
    解决 IndexedDB/Tauri Store 清空后历史会话丢失的问题。

    updatedAt 排序修复：原实现给所有会话塞 int(time.time()*1000)，
    导致前端 sort((a,b)=>b.updatedAt-a.updatedAt) 全部相等、顺序乱。
    现在用 SQLite rowid（自增 = 写入顺序 = 真实活动顺序）反推时间戳：
    - 一次 SQL 查每个 thread 的 MAX(rowid) / MIN(rowid)
    - 按 MAX(rowid) 倒序遍历，最新的 thread 拿当前时间，往前递减 1 秒
    这样既保留真实活动顺序，又是合法的递减时间戳，前端排序立即生效。
    """
    try:
        agent_obj = await get_agent()
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"message": str(e)})

    checkpointer = get_checkpointer()

    # 一次性查每个 thread 的首次/末次 rowid（写入顺序代理时间戳）
    # checkpoint_ns='' 限定根命名空间，避免子 agent 的 checkpoint 干扰
    rowid_by_thread: dict[str, tuple[int, int]] = {}  # tid -> (first_rowid, last_rowid)
    try:
        with checkpointer._lock:
            cur = checkpointer.conn.execute(
                "SELECT thread_id, MIN(rowid), MAX(rowid) "
                "FROM checkpoints WHERE checkpoint_ns = '' "
                "GROUP BY thread_id"
            )
            for row in cur.fetchall():
                rowid_by_thread[row[0]] = (row[1], row[2])
    except Exception as e:
        logger.warning("Failed to query thread rowids: %s", e)

    # 按 last_rowid 倒序排列 thread，保证最新活动的 thread 排最前
    sorted_tids = sorted(
        rowid_by_thread.keys(),
        key=lambda t: rowid_by_thread[t][1],
        reverse=True,
    )
    # 后端未命中 rowid 的（理论上不存在，防御性兜底）补到末尾
    all_tids = await checkpointer.alist_threads()
    for tid in all_tids:
        if tid not in rowid_by_thread:
            sorted_tids.append(tid)

    now_ms = int(time.time() * 1000)
    sessions_out = []
    for idx, tid in enumerate(sorted_tids):
        # 跳过后端不存在的（防御）
        if tid not in rowid_by_thread and tid not in all_tids:
            continue
        try:
            config: dict = {"configurable": {"thread_id": tid}}
            state = await agent_obj.aget_state(config)
            values = state.values or {}
            messages = values.get("messages", []) if isinstance(values, dict) else []

            title = "新对话"
            for msg in messages:
                if isinstance(msg, HumanMessage):
                    text = _extract_text(msg.content).strip()
                    if text:
                        title = text[:30] + ("..." if len(text) > 30 else "")
                        break

            # 用 rowid 顺序反推时间戳：最新 thread = now，往前每个递减 1 秒
            # 保证 updatedAt 单调递减，前端 sort 立即正确
            first_rowid, last_rowid = rowid_by_thread.get(tid, (0, 0))
            rank = idx  # 倒序排名，0=最新
            updated_ms = now_ms - rank * 1000
            # createdAt：用 first_rowid 在所有 first_rowid 中的排名反推
            # 简化：createdAt = updated_ms - (last_rowid - first_rowid) 的相对偏移
            # 这里直接用 updated_ms 作为 createdAt 兜底（前端主要用 updatedAt 排序）
            created_ms = updated_ms

            sessions_out.append({
                "id": tid,
                "title": title,
                "messageCount": len(messages),
                "createdAt": created_ms,
                "updatedAt": updated_ms,
            })
        except Exception as e:
            logger.warning("Failed to load thread %s: %s", tid, e)
            continue

    # 已经按 rowid 倒序构造，但再 sort 一次保险（也兼容 rowid 缺失的兜底场景）
    sessions_out.sort(key=lambda s: s.get("updatedAt", 0), reverse=True)
    return {"sessions": sessions_out}


@app.get("/chat/messages")
async def chat_messages(sessionId: str):
    """读取某 session 的完整历史消息，从 SqliteSaver checkpoint 恢复。

    后端是消息的唯一数据源（langgraph checkpoint 持久化在
    workspace/state/checkpoints.sqlite），前端不单独持久化消息正文，
    打开会话时调本端点把历史拉回 messagesBySession。

    返回结构对齐前端 Message 类型（src/types/domain.ts），同时附带 todos
    和 hasInterrupt，省去前端再调一次 /chat/state。
    """
    try:
        agent_obj = await get_agent()
    except RuntimeError as e:
        return JSONResponse(status_code=503, content={"message": str(e)})
    config: dict = {"configurable": {"thread_id": sessionId}}
    state = await agent_obj.aget_state(config)
    values = state.values or {}
    raw_messages = values.get("messages", []) if isinstance(values, dict) else []
    todos = values.get("todos", []) if isinstance(values, dict) else []
    messages = _map_history_messages(raw_messages, sessionId)
    interrupt_groups: list[dict] = []
    if state.next:
        from tools.ask_user_question import collect_interrupt_groups

        interrupt_groups = collect_interrupt_groups(state)
        # 将最后一条 assistant 标为 awaiting_approval，便于前端直接渲染
        if interrupt_groups:
            for msg in reversed(messages):
                if msg.get("role") == "assistant":
                    msg["status"] = "awaiting_approval"
                    msg["pendingInterruptGroups"] = interrupt_groups
                    break
    return {
        "sessionId": sessionId,
        "messages": messages,
        "todos": todos,
        "hasInterrupt": bool(interrupt_groups),
        "interruptGroups": interrupt_groups,
        "checkpointId": _checkpoint_id_from_state(state),
        "activeRunId": get_run_registry().active_run_id(sessionId),
    }


def main() -> None:
    """启动 uvicorn Web Bridge。"""
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", WEB_HOST_DEFAULT)
    token = AGENT_API_TOKEN or os.getenv("AGENT_API_TOKEN", "").strip()
    if not is_loopback_host(host) and not token:
        raise SystemExit(
            f"HOST={host!r} 为非回环地址，必须设置 AGENT_API_TOKEN 后才能启动。"
        )
    if not token:
        logger.warning(
            "AGENT_API_TOKEN 未设置：API 无鉴权。仅建议在本机回环地址使用。"
        )
    logger.info(
        "Agent Web Bridge listening on http://%s:%s (hitl=%s cors=%s)",
        host,
        port,
        HITL_ENABLED,
        ALLOWED_ORIGINS,
    )
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
