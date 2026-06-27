from deepagents import create_deep_agent
import os
import logging
from dotenv import load_dotenv
from langfuse import get_client
from langfuse.langchain import CallbackHandler
import uuid
from langchain_core.messages import AIMessageChunk, ToolMessage
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
import re
import base64
import mimetypes
from urllib.request import urlopen

from agent_runtime import create_llm, backend, web_search, get_current_time

load_dotenv()

# 开启 deepagents 日志，至少能看到 skill 加载错误
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("deepagents").setLevel(logging.DEBUG)

llm = create_llm()

system_prompt = "你是权哥的助手，你叫做小权，你的任务是帮助权哥完成各种任务。"

langfuse = get_client()
agent = create_deep_agent(
    model=llm,
    system_prompt=system_prompt,
    backend=backend,
    tools=[web_search,get_current_time],
    interrupt_on={"web_search": True, "execute": True},
    checkpointer=MemorySaver(),
    skills=["skills/"],
)

# 启动时检查 skill 加载情况
import os as _os
_skills_dir = _os.path.join("workspace", "skills")
print(f"\n[SKILL 检查] skills 目录: {_os.path.abspath(_skills_dir)}")
if _os.path.isdir(_skills_dir):
    for _name in _os.listdir(_skills_dir):
        _skill_md = _os.path.join(_skills_dir, _name, "SKILL.md")
        _status = "✅ 找到" if _os.path.isfile(_skill_md) else "❌ 缺失"
        print(f"  - {_name}: {_status} SKILL.md")
else:
    print(f"  ❌ 目录不存在: {_skills_dir}")
print()

session_id = str(uuid.uuid4())
turn_count = 0
langfuse_handler = CallbackHandler()
_pending_tool_calls = {}  # 累积流式工具调用分片，key=index


def log_tool_call(msg_chunk):
    """累积流式分片，等工具调用完整后一次性打印"""
    # 累积 AIMessageChunk 中的工具调用分片
    tool_calls = getattr(msg_chunk, "tool_call_chunks", None) or []
    for tc in tool_calls:
        idx = tc.get("index", 0)
        if idx not in _pending_tool_calls:
            _pending_tool_calls[idx] = {"name": "", "args": ""}
        if tc.get("name"):
            _pending_tool_calls[idx]["name"] += tc["name"]
        if tc.get("args"):
            _pending_tool_calls[idx]["args"] += tc["args"]

    # 工具执行完成时（ToolMessage）统一输出完整调用
    if isinstance(msg_chunk, ToolMessage):
        name = msg_chunk.name or ""
        content_preview = str(msg_chunk.content)[:300]
        # 从累积的分片中找对应参数
        args_str = ""
        tool_call_id = getattr(msg_chunk, "tool_call_id", "")
        for tc in _pending_tool_calls.values():
            if tc["name"] == name:
                args_str = tc["args"]
                break

        if name == "read_file" and "SKILL.md" in args_str:
            print(f"\n🔧 [SKILL 激活] {name}({args_str})", flush=True)
        else:
            print(f"\n🛠️ [工具调用] {name}({args_str})", flush=True)
        print(f"📋 [工具结果] {content_preview}{'...' if len(str(msg_chunk.content)) > 300 else ''}", flush=True)

# === 多模态支持：把图片 URL 转成 OpenAI 格式 ===
IMAGE_URL_RE = re.compile(
    r'https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s]*)?',
    re.IGNORECASE,
)

def to_image_part(url: str) -> dict:
    """把图片引用转成 OpenAI image_url part。HTTP URL 先下载再 base64。"""
    if url.startswith("data:"):
        return {"type": "image_url", "image_url": {"url": url}}
    if url.startswith(("http://", "https://")):
        data = urlopen(url, timeout=10).read()
        mime, _ = mimetypes.guess_type(url)
        mime = mime or "image/jpeg"
        b64 = base64.b64encode(data).decode("ascii")
        return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}"}}
    raise ValueError(f"不支持的图片引用: {url}")

def build_user_content(text: str, image_urls: list[str]) -> str | list[dict]:
    """没图 → 返回字符串；    有图 → 返回 list[dict] 多模态 content。"""
    if not image_urls:
        return text
    parts = [to_image_part(u) for u in image_urls]
    parts.append({"type": "text", "text": text})
    return parts
# =============================================

while True:
    user_input = input("\n👤 你: ")
    if user_input.lower() == "exit":
        print("小权: 再见！")
        break

    turn_count += 1
    need_prefix = True

    config = {
        "callbacks": [langfuse_handler],
        "configurable": {
            "thread_id": session_id,
        },
        "run_name": f"turn{turn_count}: {user_input[:20]}{'…' if len(user_input) > 20 else ''}",
        "metadata": {
            "langfuse_session_id": session_id,
            "langfuse_tags": ["deepagents"],
        },
    }

    try:
        # === 多模态：扫消息里的图片 URL ===
        image_urls = IMAGE_URL_RE.findall(user_input)
        text = IMAGE_URL_RE.sub('', user_input).strip() or "请描述这张图"
        try:
            user_content = build_user_content(text, image_urls)
        except Exception as e:
            print(f"\n⚠️ 加载图片失败: {e}")
            user_content = text
        # ===================================

        _pending_tool_calls.clear()  # 清空上一轮的工具调用分片
        for msg_chunk, _meta in agent.stream(
            {"messages": [{"role": "user", "content": user_content}]},
            stream_mode="messages",
            config=config,
        ):
            log_tool_call(msg_chunk)
            if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                print(f"{'小权: ' if need_prefix else ''}{msg_chunk.content}", end="", flush=True)
                need_prefix = False
        print()
    except Exception as e:
        print(f"\n⚠️ 异常: {type(e).__name__}: {e}")

    state_check = agent.get_state(config)
    print(f"[DEBUG] 首次stream后 state.next={state_check.next}")

    # HITL 循环：可能多轮中断，每轮恢复后都要再检查
    while True:
        state = agent.get_state(config)
        if not state.next:
            break  # 没有挂起的中断，退出循环

        # 从中断信息里提取所有 action_requests
        all_action_requests = []
        for task in state.tasks:
            for interrupt in task.interrupts:
                action_requests = interrupt.value.get("action_requests", [])
                all_action_requests.extend(action_requests)

        if not all_action_requests:
            print(f"\n[DEBUG] state.next={state.next} 但无 action_requests，中断值：", [t.interrupts for t in state.tasks])
            break

        # 逐个确认每个工具调用
        decisions = []
        for i, req in enumerate(all_action_requests, 1):
            tool_name = req.get("name", "未知工具")
            tool_args = req.get("args", {})
            print(f"\n⚠️ [{i}/{len(all_action_requests)}] 需要确认：是否允许调用 [{tool_name}]？")
            print(f"   参数: {tool_args}")

            user_decision = input("   输入 y 批准 / n 拒绝: ").strip().lower()
            if user_decision == "y":
                print("   ✅ 已批准")
                decisions.append({"type": "approve"})
            else:
                print("   ❌ 已拒绝")
                decisions.append({"type": "reject"})

        # 恢复执行：传入所有 decisions
        print(f"\n[DEBUG] 恢复执行，decisions={decisions}")
        need_prefix = True
        try:
            _pending_tool_calls.clear()  # 清空上一轮的工具调用分片
            for msg_chunk, _meta in agent.stream(
                Command(resume={"decisions": decisions}),
                config=config,
                stream_mode="messages",
            ):
                log_tool_call(msg_chunk)
                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                    print(f"{'小权: ' if need_prefix else ''}{msg_chunk.content}", end="", flush=True)
                    need_prefix = False
            print()
        except Exception as e:
            print(f"\n⚠️ 恢复执行异常: {type(e).__name__}: {e}")

        # 恢复后再检查一轮（Agent 可能再次触发中断）
        state_after = agent.get_state(config)
        print(f"[DEBUG] 恢复后 state.next={state_after.next}")
        if not state_after.next:
            break
