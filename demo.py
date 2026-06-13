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
    tools=[web_search,get_current_time]
)
session_id = str(uuid.uuid4())
turn_count = 0
langfuse_handler = CallbackHandler()

while True:
    user_input = input("\n👤 你: ")
    if user_input.lower() == "exit":
        print("小权: 再见！")
        break

    turn_count += 1
    need_prefix = True
    for msg_chunk, _meta in agent.stream(
        {"messages": [("human", user_input)]},
        stream_mode="messages",
        config={
            "callbacks": [langfuse_handler],
            "run_name": f"turn{turn_count}: {user_input[:20]}{'…' if len(user_input) > 20 else ''}",
            "metadata": {
                "langfuse_session_id": session_id,
                "langfuse_tags": ["deepagents"],
            },
        },
    ):
        if msg_chunk.content:
            print(f"{'小权: ' if need_prefix else ''}{msg_chunk.content}", end="", flush=True)
            need_prefix = False
    print()