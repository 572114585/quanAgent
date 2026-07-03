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
import json
import logging
import mimetypes
import os
import time
import uuid
from pathlib import Path
from typing import AsyncGenerator

from dotenv import load_dotenv
from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from langchain_core.messages import AIMessageChunk, ToolMessage
from langgraph.types import Command
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# === 复用 agent_core：build_agent 工厂 + 配置常量 ===
load_dotenv()

from agent_core import build_agent  # noqa: E402
from agent_core.config import (  # noqa: E402
    HITL_ENABLED_DEFAULT as HITL_ENABLED,
    LOG_LEVEL,
    MAX_UPLOAD_SIZE,
    OUTPUT_DIR,
    UPLOADS_DIR,
)
from artifacts import detect_new_artifacts, snapshot_output_dir  # noqa: E402

try:
    from langfuse.langchain import CallbackHandler as _LangfuseCallbackHandler

    _langfuse_available = True
except Exception:  # langfuse 未配置时降级
    _LangfuseCallbackHandler = None
    _langfuse_available = False


# === 日志 ===
logging.basicConfig(
    level=LOG_LEVEL,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent-web")


# === Agent 单例（与 agent_core.agent 同配置，但 HITL 开关独立） ===
# uvicorn 在单 event loop 内并发多请求，首请求初始化期间若无锁，
# 并发的第二个请求会重复进入初始化分支，创建多个 agent 并覆盖单例。
# 用 asyncio.Lock 保护：首个协程持锁初始化，其余等待。
_agent_singleton: object | None = None
_agent_init_error: str | None = None
_agent_init_lock = asyncio.Lock()


async def get_agent() -> object:
    """懒加载 + 单例（asyncio.Lock 保护并发）。初始化失败时持久化错误状态，避免每次请求都重试。"""
    global _agent_singleton, _agent_init_error

    # 失败后不再重试：直接返回持久化错误
    if _agent_init_error is not None:
        raise RuntimeError(f"Agent initialization failed: {_agent_init_error}")

    if _agent_singleton is not None:
        return _agent_singleton

    async with _agent_init_lock:
        # 双检：持锁后可能已有协程完成初始化
        if _agent_init_error is not None:
            raise RuntimeError(f"Agent initialization failed: {_agent_init_error}")
        if _agent_singleton is not None:
            return _agent_singleton

        try:
            agent = build_agent(hitl=HITL_ENABLED)
            _agent_singleton = agent
            logger.info("Agent initialized (hitl=%s)", HITL_ENABLED)
        except Exception as e:
            error_msg = str(e)
            _agent_init_error = error_msg
            logger.error("Agent initialization failed, error persisted: %s", error_msg)
            raise RuntimeError(f"Agent initialization failed: {error_msg}") from e

    return _agent_singleton


# === FastAPI 应用 ===
app = FastAPI(title="Agent Web Bridge", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # dev only
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

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


class ResumeRequest(BaseModel):
    sessionId: str
    # 每个 interrupt 一组决定，与 interrupt 事件的 groups 一一对应。
    # LangGraph 多 interrupt 恢复必须按 interrupt_id 索引：
    # https://docs.langchain.com/oss/python/langgraph/add-human-in-the-loop#resume-multiple-interrupts-with-one-invocation
    decisions: list[dict] = Field(
        ...,
        description='[{"interruptId": "...", "decisions": [{"type": "approve" | "reject"}, ...]}, ...]',
    )


# === 附件处理 ===

def _get_local_path(remote_url: str) -> str:
    """将 /uploads/xxx.pdf 转换为相对路径 uploads/xxx.pdf。"""
    return remote_url.lstrip("/") if remote_url.startswith("/") else remote_url


def _build_attachment_context(attachments: list[Attachment]) -> str:
    """将所有附件信息构建为给 agent 的提示上下文。

    图片和文档统一处理：告知 agent 文件路径和可用的工具。
    当前 LLM 不支持多模态 vision，图片无法直接"看见"，需告知用户限制。
    """
    if not attachments:
        return ""

    images = [a for a in attachments if a.mime.startswith("image/")]
    docs = [a for a in attachments if not a.mime.startswith("image/")]

    lines = ["\n\n---", "## 用户上传的附件"]

    if images:
        lines.append("")
        lines.append(f"用户上传了 {len(images)} 张图片（当前模型不支持图片视觉识别，无法直接查看图片内容）：")
        lines.append("")
        for img in images:
            size_kb = img.size / 1024 if img.size else 0
            local_path = _get_local_path(img.remoteUrl)
            lines.append(f"- 🖼️ **{img.name}**（{img.mime}, {size_kb:.1f} KB）：`{local_path}`")
        lines.append("")
        lines.append("提示：如果用户要求识别图片内容，请告知当前模型不支持图片视觉理解，建议用户描述图片内容或使用支持 vision 的模型。")

    if docs:
        if images:
            lines.append("")
        lines.append("以下文档文件已上传到本地，你可以使用 mineru skill 解析这些文档：")
        lines.append("")
        for doc in docs:
            size_kb = doc.size / 1024 if doc.size else 0
            local_path = _get_local_path(doc.remoteUrl)
            lines.append(f"- 📄 **{doc.name}**（{doc.mime}, {size_kb:.1f} KB）：`{local_path}`")
        lines.append("")
        lines.append("解析文档的方法：使用 execute 工具运行 mineru skill 的 extract.py 脚本。")
        lines.append("示例命令：")
        lines.append("```")
        lines.append(f"python skills/mineru/scripts/extract.py {_get_local_path(docs[0].remoteUrl)} -o output/parsed.md")
        lines.append("```")
        lines.append("解析完成后，读取 output/parsed.md 即可获取文档内容，再据此回答用户问题。")
        lines.append("如果用户的消息为空或仅要求解析/总结文档，请先执行解析，再根据解析结果作答。")

    return "\n".join(lines)


# === SSE 工具 ===
def _sse(payload: dict) -> dict:
    return {"event": "message", "data": json.dumps(payload, ensure_ascii=False)}


def _open_langfuse_trace(session_id: str, run_name: str):
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
        # 同一会话的多次请求（含 HITL resume）通过 langfuse_session_id 归并到
        # langfuse UI 的同一个 session 视图。
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": ["deepagents", "web"],
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
        metadata={"session_id": session_id, "tags": ["deepagents", "web"]},
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
    output = str(msg_chunk.content)[:500]

    yield _sse({
        "type": "tool_call",
        "callId": call_id,
        "name": pending.get("name", name) if pending else name,
        "args": args_value,
        "subagentId": subagent_id,
    })
    yield _sse({
        "type": "tool_result",
        "callId": call_id,
        "name": name,
        "output": output,
        "subagentId": subagent_id,
    })
    pending_tools.clear()


async def _stream_agent(
    agent_obj,
    input_payload: dict,
    config: dict,
    message_id: str,
) -> AsyncGenerator[dict, None]:
    """通用流式生成器：处理 stream + HITL 检查 + 收尾事件。

    注意：
    1. 必须是 async def，否则返回的是普通生成器，
       sse_starlette 的 EventSourceResponse 会用 async for 遍历，
       'async for' over sync generator 会报 TypeError。
    2. 必须用 astream() 而不是 stream()，否则同步迭代会阻塞 asyncio 事件循环，
       sse_starlette 无法及时 flush 数据到 socket。
    """
    started_at = time.time()
    try:
        yield _sse({"type": "start", "messageId": message_id})

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
                    })
                sub_state = active_subagents[subagent_id]
                if isinstance(msg_chunk, ToolMessage):
                    # 子 agent 内部工具返回 = 嵌套步骤
                    async for evt in _emit_subagent_tool_events(
                        msg_chunk, sub_state["pending_tools"], subagent_id
                    ):
                        yield evt
                elif isinstance(msg_chunk, AIMessageChunk):
                    # 累积子 agent 内部工具调用分片（用于 ToolMessage 时取 args）
                    _accumulate_tool_call_chunks(msg_chunk, sub_state["pending_tools"])
                # 子 agent chunk 一律不进入下方父图分支
                continue

            if isinstance(msg_chunk, AIMessageChunk):
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
                    yield _sse({"type": "thinking_delta", "delta": reasoning_content})
                if content:
                    # 基于消息结构路由（不依赖模型输出文本标记）：
                    # - 当前 AIMessage 轮有 tool_call_chunks → 工具调用轮的过渡语 → thinking
                    # - 无 tool_call_chunks → 最终答案 → delta
                    if current_ai_has_tool_calls:
                        yield _sse({"type": "thinking_delta", "delta": content})
                    else:
                        yield _sse({"type": "delta", "delta": content})
                if not content and not reasoning_content:
                    # 没文本但有 chunk（如纯工具调用）→ 给前端一个思考指示
                    yield _sse({"type": "thinking"})
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
                    yield _sse({"type": "subagent_done", "subagentId": ckpt_ns})
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
                    })
                    yield _sse({"type": "subagent_done", "subagentId": fallback_id})
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
                    })
                    # 2) 再发 tool_result：补全同 callId 的 output / status=completed
                    yield _sse({
                        "type": "tool_result",
                        "callId": call_id,
                        "name": name,
                        "output": str(msg_chunk.content)[:500],
                    })
                else:
                    # pending 找不到（tool_call_chunks 未累积到 name），
                    # 不再降级发旧 tool 事件（会污染 content），统一发 tool_call + tool_result
                    call_id = tool_call_id or f"tc_{uuid.uuid4().hex[:8]}"
                    yield _sse({
                        "type": "tool_call",
                        "callId": call_id,
                        "name": name,
                        "args": "",
                    })
                    yield _sse({
                        "type": "tool_result",
                        "callId": call_id,
                        "name": name,
                        "output": str(msg_chunk.content)[:500],
                    })

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

        # 检查 HITL 中断
        # 必须用 aget_state（异步）：get_state 是同步阻塞调用，
        # 在 async 上下文里会卡住事件循环，导致 SSE 数据无法 flush。
        state = await agent_obj.aget_state(config)
        if state.next:
            # 按 interrupt 分组：每个 Interrupt 自带 id，恢复时必须按 id 索引，
            # 否则多 pending interrupt 会报 RuntimeError：
            #   "When there are multiple pending interrupts, you must specify the interrupt id when resuming"
            # 单个 interrupt 内可能含多个 action_request（并发工具调用），共享同一 id。
            groups: list[dict] = []
            for task in state.tasks:
                for intr in task.interrupts:
                    action_requests = intr.value.get("action_requests", [])
                    if action_requests:
                        groups.append(
                            {"interruptId": intr.id, "toolCalls": action_requests}
                        )
            if groups:
                yield _sse({"type": "interrupt", "groups": groups})

        logger.info(
            "stream done messageId=%s events=%d duration=%.2fs",
            message_id,
            event_count,
            time.time() - started_at,
        )
        yield _sse({"type": "done", "messageId": message_id})
    except Exception as e:  # noqa: BLE001
        logger.exception("Stream error")
        yield _sse({"type": "error", "message": f"{type(e).__name__}: {e}"})
        yield _sse({"type": "done", "messageId": message_id})


async def _stream_with_artifacts(
    agent_obj,
    input_payload,
    config: dict,
    message_id: str,
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
    async for evt in _stream_agent(agent_obj, input_payload, config, message_id):
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
            yield _sse({"type": "artifact", **art})
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
async def chat(req: ChatRequest):
    attachment_context = _build_attachment_context(req.attachments)
    user_message = req.message + attachment_context if attachment_context else req.message
    user_content: str | list[dict] = user_message

    try:
        agent_obj = await get_agent()
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )
    message_id = str(uuid.uuid4())
    config, _trace_id = _open_langfuse_trace(req.sessionId, f"chat:{req.message[:20]}")
    logger.info(
        "chat session=%s msg=%r attachments=%d",
        req.sessionId,
        req.message[:40],
        len(req.attachments),
    )

    async def event_stream() -> AsyncGenerator[dict, None]:
        async for evt in _stream_with_artifacts(
            agent_obj,
            {"messages": [{"role": "user", "content": user_content}]},
            config,
            message_id,
        ):
            yield evt

    return EventSourceResponse(event_stream(), ping=15)


@app.post("/chat/resume")
async def resume(req: ResumeRequest):
    """HITL 中断后提交用户决定，继续流式输出。"""
    try:
        agent_obj = await get_agent()
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )
    message_id = str(uuid.uuid4())
    config, _trace_id = _open_langfuse_trace(req.sessionId, f"resume:{req.sessionId[:8]}")
    logger.info("resume session=%s decisions=%s", req.sessionId, req.decisions)

    async def event_stream() -> AsyncGenerator[dict, None]:
        # LangGraph 多 interrupt 恢复：Command(resume={interrupt_id: value, ...})
        # 单次调用同时恢复所有 pending interrupt，避免 chained SSE。
        # 见 https://docs.langchain.com/oss/python/langgraph/add-human-in-the-loop#resume-multiple-interrupts-with-one-invocation
        resume_map: dict = {
            item["interruptId"]: {"decisions": item["decisions"]}
            for item in req.decisions
        }
        async for evt in _stream_with_artifacts(
            agent_obj,
            Command(resume=resume_map),
            config,
            message_id,
        ):
            yield evt

    return EventSourceResponse(event_stream(), ping=15)


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
    if state.next:
        for task in state.tasks:
            for intr in task.interrupts:
                interrupts.extend(intr.value.get("action_requests", []))
    values = state.values or {}
    todos = values.get("todos", []) if isinstance(values, dict) else []
    messages = values.get("messages", []) if isinstance(values, dict) else []
    return {
        "sessionId": sessionId,
        "hasInterrupt": bool(state.next),
        "interrupts": interrupts,
        "todos": todos,
        "messageCount": len(messages),
    }


def main() -> None:
    """启动 uvicorn Web Bridge。"""
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info("Agent Web Bridge listening on http://%s:%s (hitl=%s)", host, port, HITL_ENABLED)
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
