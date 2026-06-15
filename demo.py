from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
import os
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv
from ducktools import web_search
from time_tools import get_current_time
from langfuse import get_client
from langfuse.langchain import CallbackHandler
import uuid
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command
import re
import base64
import mimetypes
from urllib.request import urlopen

load_dotenv()

llm = ChatOpenAI(
    model="agnes-2.0-flash",
    base_url="https://apihub.agnes-ai.com/v1/chat/completions",
    api_key=os.getenv("OPENAI_API_KEY"))

system_prompt = "你是权哥的助手，你叫做小权，你的任务是帮助权哥完成各种任务。"

filebackend = FilesystemBackend(
    root_dir="workspace",
    virtual_mode=True
)

langfuse = get_client()
agent = create_deep_agent(
    model=llm,
    system_prompt=system_prompt,
    backend=filebackend,
    tools=[web_search,get_current_time],
    interrupt_on={"web_search": True},
    checkpointer=MemorySaver(),
)
session_id = str(uuid.uuid4())
turn_count = 0
langfuse_handler = CallbackHandler()

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

        for msg_chunk, _meta in agent.stream(
            {"messages": [{"role": "user", "content": user_content}]},
            stream_mode="messages",
            config=config,
        ):
            if msg_chunk.content:
                print(f"{'小权: ' if need_prefix else ''}{msg_chunk.content}", end="", flush=True)
                need_prefix = False
        print()
    except Exception as e:
        print(f"\n⚠️ 异常: {type(e).__name__}: {e}")

    state = agent.get_state(config)
    if state.next:
        # 从中断信息里提取 tool 名和参数
        for task in state.tasks:
            for interrupt in task.interrupts:
                action_requests = interrupt.value.get("action_requests", [])
                for req in action_requests:
                    tool_name = req.get("name", "未知工具")
                    tool_args = req.get("args", {})
                    print(f"\n⚠️ 需要确认：是否允许调用 [{tool_name}]？")
                    print(f"   参数: {tool_args}")

        # 问用户
        user_decision = input("   输入 y 批准 / n 拒绝: ").strip().lower()

        if user_decision == "y":
            print("   ✅ 已批准，继续执行...")
            # 恢复执行：approve
            need_prefix = True
            for msg_chunk, _meta in agent.stream(
                Command(resume={"decisions": [{"type": "approve"}]}),
                config=config,
                stream_mode="messages",
            ):
                if msg_chunk.content:
                    print(f"{'小权: ' if need_prefix else ''}{msg_chunk.content}", end="", flush=True)
                    need_prefix = False
            print()
        else:
            print("   ❌ 已拒绝")
            # 恢复执行：reject
            agent.invoke(Command(resume={"decisions": [{"type": "reject"}]}), config=config)
