"""
Agent Web Bridge —— 把 agent_runtime 的 deep agent 暴露为 HTTP + SSE 端点。

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
    data: {"type":"tool_call","callId":"...","name":"...","args":...}  ← 模型决定调工具
    data: {"type":"tool_result","callId":"...","name":"...","output":...}  ← 工具执行返回
    data: {"type":"tool","name":"...","args":...,"preview":"..."}    ← 旧协议兼容（降级路径）
    data: {"type":"interrupt","toolCalls":[{"name":"...","args":{...}}]}
    data: {"type":"usage","promptTokens":N,"completionTokens":M}
    data: {"type":"done","messageId":"..."}
    data: {"type":"error","message":"..."}

设计原则：
    - 复用 agent_runtime.py 的所有工厂（create_llm / backend / SYSTEM_PROMPT），
      不复制 LLM、tool、prompt 逻辑
    - CLI 模式（demo.py）和 Web 模式（run.py）共享同一个 agent 定义
    - 工具调用分片累积只在 log_tool_call 里做；流式只把 ToolMessage 完整体推给前端
    - 思考 vs 最终答案：基于消息结构判断，不依赖模型输出文本标记
      · reasoning_content / 工具调用轮的 content → thinking_delta（折叠区）
      · 无 tool_call_chunks 的 AIMessageChunk content → delta（最终答案区）
"""
from __future__ import annotations

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
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
from pydantic import BaseModel, Field
from sse_starlette.sse import EventSourceResponse

# === 复用 agent_runtime：LLM / 后端 / 提示词 / 工具 / langfuse ===
load_dotenv()
from deepagents import create_deep_agent  # noqa: E402

from agent_runtime import (  # noqa: E402
    SYSTEM_PROMPT,
    backend,
    create_llm,
    render_html,
)
from ducktools import web_search  # noqa: E402
from time_tools import get_current_time  # noqa: E402

try:
    from langfuse.langchain import CallbackHandler

    _langfuse_handler = CallbackHandler()
except Exception:  # langfuse 未配置时降级
    _langfuse_handler = None


# === 日志 ===
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("agent-web")


# === HITL 开关：可通过环境变量覆盖 ===
HITL_ENABLED = os.getenv("HITL_ENABLED", "true").lower() in ("1", "true", "yes")

# === 文件上传限制 ===
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))  # 20MB

# === Agent 单例（与 agent_runtime.agent 同配置，但 HITL 开关独立） ===
_agent_lock_key = "_agent_singleton"
_agent_error_key = "_agent_init_error"


def build_agent(hitl: bool):
    """根据 hitl 标志创建 deep agent。所有工具、后端、提示词复用 agent_runtime。"""
    interrupt_on = {"web_search": hitl, "execute": hitl} if hitl else None
    logger.info(
        "build_agent(hitl=%s) interrupt_on=%s",
        hitl,
        interrupt_on,
    )
    return create_deep_agent(
        model=create_llm(),
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        tools=[web_search, get_current_time, render_html],
        interrupt_on=interrupt_on,
        checkpointer=MemorySaver(),
        skills=["skills/"],
    )


def get_agent() -> object:
    """懒加载 + 单例。初始化失败时持久化错误状态，避免每次请求都重试。"""
    cached_error = getattr(get_agent, _agent_error_key, None)
    if cached_error is not None:
        raise RuntimeError(f"Agent initialization failed: {cached_error}")

    if not hasattr(get_agent, _agent_lock_key):
        try:
            agent = build_agent(HITL_ENABLED)
            setattr(get_agent, _agent_lock_key, agent)
            logger.info("Agent initialized (hitl=%s)", HITL_ENABLED)
        except Exception as e:
            error_msg = str(e)
            setattr(get_agent, _agent_error_key, error_msg)
            logger.error("Agent initialization failed, error persisted: %s", error_msg)
            raise RuntimeError(f"Agent initialization failed: {error_msg}") from e
    return getattr(get_agent, _agent_lock_key)


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
UPLOAD_DIR = Path("workspace/uploads")
OUTPUT_DIR = Path("workspace/output")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")
app.mount("/output", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")


def _snapshot_output_dir() -> set[tuple[str, int]]:
    """Take a snapshot of output/ directory: set of (relative_path, file_size)."""
    snapshot: set[tuple[str, int]] = set()
    for f in OUTPUT_DIR.rglob("*"):
        if f.is_file():
            try:
                rel = f.relative_to(OUTPUT_DIR).as_posix()
                snapshot.add((rel, f.stat().st_size))
            except OSError:
                continue
    return snapshot


def _detect_new_artifacts(before: set[tuple[str, int]]) -> list[dict]:
    """Compare current output/ with the before snapshot, return list of artifact metadata dicts."""
    after = _snapshot_output_dir()
    new_files = after - before
    artifacts = []
    mime_map = {
        ".pdf": "application/pdf",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ".ppt": "application/vnd.ms-powerpoint",
        ".csv": "text/csv",
        ".txt": "text/plain",
        ".md": "text/markdown",
        ".json": "application/json",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".html": "text/html",
        ".zip": "application/zip",
    }
    for rel_path, size in new_files:
        name = Path(rel_path).name
        ext = Path(rel_path).suffix.lower()
        mime = mime_map.get(ext, mimetypes.guess_type(name)[0] or "application/octet-stream")
        artifacts.append({
            "name": name,
            "path": rel_path,
            "url": f"/output/{rel_path}",
            "mime": mime,
            "size": size,
        })
    artifacts.sort(key=lambda a: a["name"])
    return artifacts


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
    decisions: list[dict] = Field(..., description='[{"type": "approve"} | {"type": "reject"}]')


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
        lines.append("以下文档文件已上传到本地，你可以使用 document-parser skill 解析这些文档：")
        lines.append("")
        for doc in docs:
            size_kb = doc.size / 1024 if doc.size else 0
            local_path = _get_local_path(doc.remoteUrl)
            lines.append(f"- 📄 **{doc.name}**（{doc.mime}, {size_kb:.1f} KB）：`{local_path}`")
        lines.append("")
        lines.append("解析文档的方法：使用 execute 工具运行 document-parser skill 的 parse.py 脚本。")
        lines.append("示例命令：")
        lines.append("```")
        lines.append(f"python skills/document-parser/scripts/parse.py --file {_get_local_path(docs[0].remoteUrl)} --out output/parsed.md")
        lines.append("```")
        lines.append("解析完成后，读取 output/parsed.md 即可获取文档内容，再据此回答用户问题。")
        lines.append("如果用户的消息为空或仅要求解析/总结文档，请先执行解析，再根据解析结果作答。")

    return "\n".join(lines)


# === SSE 工具 ===
def _sse(payload: dict) -> dict:
    return {"event": "message", "data": json.dumps(payload, ensure_ascii=False)}


def _build_config(session_id: str, run_name: str) -> dict:
    cfg: dict = {
        "configurable": {"thread_id": session_id},
        "run_name": run_name,
    }
    if _langfuse_handler is not None:
        cfg["callbacks"] = [_langfuse_handler]
    return cfg


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

        # 工具调用分片累积（与 demo.py 的 log_tool_call 一致）
        # pending_tool_calls 记录从 AIMessageChunk.tool_call_chunks 里拼出来的工具调用
        # —— 这些是"模型决定调工具"的元数据，进入思考区（独立于最终答案）。
        pending_tool_calls: dict[int, dict] = {}
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
        astream_fn = getattr(agent_obj, "astream", None)
        if astream_fn is not None:
            stream_iter = astream_fn(
                input_payload, config=config, stream_mode="messages"
            )
        else:
            import asyncio

            loop = asyncio.get_running_loop()

            def _gen():
                yield from agent_obj.stream(
                    input_payload, config=config, stream_mode="messages"
                )

            stream_iter = _aiter_from_sync(loop, _gen())

        async for msg_chunk, _meta in stream_iter:
            event_count += 1
            logger.debug(
                "stream chunk #%d type=%s preview=%s",
                event_count,
                type(msg_chunk).__name__,
                str(getattr(msg_chunk, "content", ""))[:80],
            )

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
            if tool_call_chunks:
                # 当前 AIMessage 轮出现了工具调用 → 标记为工具调用轮
                # 此轮的 content 会走 thinking_delta
                current_ai_has_tool_calls = True
            for tc in tool_call_chunks:
                idx = tc.get("index", 0)
                if idx not in pending_tool_calls:
                    pending_tool_calls[idx] = {"id": "", "name": "", "args": ""}
                if tc.get("id"):
                    pending_tool_calls[idx]["id"] = tc["id"]
                if tc.get("name"):
                    pending_tool_calls[idx]["name"] += tc["name"]
                if tc.get("args"):
                    pending_tool_calls[idx]["args"] += tc["args"]

        # 检查 HITL 中断
        state = agent_obj.get_state(config)
        if state.next:
            interrupts: list[dict] = []
            for task in state.tasks:
                for intr in task.interrupts:
                    action_requests = intr.value.get("action_requests", [])
                    interrupts.extend(action_requests)
            if interrupts:
                yield _sse({"type": "interrupt", "toolCalls": interrupts})

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
            "upload_dir": str(UPLOAD_DIR.resolve()),
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
    target = UPLOAD_DIR / safe_name
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
        agent_obj = get_agent()
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )
    message_id = str(uuid.uuid4())
    config = _build_config(req.sessionId, f"chat:{req.message[:20]}")
    logger.info(
        "chat session=%s msg=%r attachments=%d",
        req.sessionId,
        req.message[:40],
        len(req.attachments),
    )

    async def event_stream() -> AsyncGenerator[dict, None]:
        snapshot_before = _snapshot_output_dir()
        done_evt = None
        async for evt in _stream_agent(
            agent_obj,
            {"messages": [{"role": "user", "content": user_content}]},
            config,
            message_id,
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
            new_artifacts = _detect_new_artifacts(snapshot_before)
            for art in new_artifacts:
                yield _sse({"type": "artifact", **art})
            if new_artifacts:
                logger.info("Detected %d new artifact(s) in output/", len(new_artifacts))
            yield done_evt

    return EventSourceResponse(event_stream(), ping=15)


@app.post("/chat/resume")
async def resume(req: ResumeRequest):
    """HITL 中断后提交用户决定，继续流式输出。"""
    try:
        agent_obj = get_agent()
    except RuntimeError as e:
        return JSONResponse(
            status_code=503,
            content={"message": str(e)},
        )
    message_id = str(uuid.uuid4())
    config = _build_config(req.sessionId, f"resume:{req.sessionId[:8]}")
    logger.info("resume session=%s decisions=%s", req.sessionId, req.decisions)

    async def event_stream() -> AsyncGenerator[dict, None]:
        snapshot_before = _snapshot_output_dir()
        done_evt = None
        async for evt in _stream_agent(
            agent_obj,
            Command(resume={"decisions": req.decisions}),
            config,
            message_id,
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
            new_artifacts = _detect_new_artifacts(snapshot_before)
            for art in new_artifacts:
                yield _sse({"type": "artifact", **art})
            if new_artifacts:
                logger.info("Detected %d new artifact(s) in output/", len(new_artifacts))
            yield done_evt

    return EventSourceResponse(event_stream(), ping=15)


# === 启动 ===
if __name__ == "__main__":
    import uvicorn

    port = int(os.getenv("PORT", "8000"))
    host = os.getenv("HOST", "0.0.0.0")
    logger.info("Agent Web Bridge listening on http://%s:%s (hitl=%s)", host, port, HITL_ENABLED)
    uvicorn.run(app, host=host, port=port, log_level="info")
