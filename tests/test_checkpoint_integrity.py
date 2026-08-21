import sqlite3
import shutil
import tempfile
from pathlib import Path

import pytest
from deepagents import create_deep_agent
from langchain_core.language_models.fake_chat_models import FakeMessagesListChatModel
from langchain_core.messages import AIMessage
from langchain_core.tools import tool
from langgraph.types import Command

from agent_core.runtime import DualSqliteSaver
from tools.ask_user_question import ask_user_question, collect_interrupt_groups
from tools.checkpoint_maintenance import compact_thread, maintain_checkpoint_db


class ToolCapableFakeModel(FakeMessagesListChatModel):
    def bind_tools(self, tools, **kwargs):  # noqa: ARG002
        return self


@tool
def checkpoint_echo(value: str) -> str:
    """Return a value so the test creates a real tool-message pair."""
    return value


def _assert_tool_messages_are_paired(messages):
    for index, message in enumerate(messages):
        if getattr(message, "type", None) != "tool":
            continue
        assert index > 0
        previous = messages[index - 1]
        calls = getattr(previous, "tool_calls", None) or []
        assert any(
            call.get("id") == message.tool_call_id
            for call in calls
            if isinstance(call, dict)
        )


@pytest.mark.asyncio
async def test_checkpoint_maintenance_preserves_tool_history():
    temp_dir = Path(tempfile.mkdtemp(prefix="checkpoint-integrity-"))
    db_path = temp_dir / "checkpoints.sqlite"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    saver = DualSqliteSaver(conn)
    saver.setup()
    model = ToolCapableFakeModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "checkpoint_echo",
                        "args": {"value": "x"},
                        "id": "echo-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ask_user_question",
                        "args": {
                            "title": "T",
                            "questions": [{"id": "q", "prompt": "P"}],
                        },
                        "id": "ask-1",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(content="done"),
        ]
    )
    agent = create_deep_agent(
        model=model,
        tools=[checkpoint_echo, ask_user_question],
        checkpointer=saver,
        interrupt_on={},
    )
    config = {"configurable": {"thread_id": "checkpoint-integrity"}}

    try:
        async for _ in agent.astream(
            {"messages": [{"role": "user", "content": "go"}]},
            config=config,
            stream_mode="values",
        ):
            pass

        before = await agent.aget_state(config)
        assert collect_interrupt_groups(before)
        root_count_before = conn.execute(
            "SELECT count(*) FROM checkpoints "
            "WHERE thread_id=? AND checkpoint_ns=''",
            ("checkpoint-integrity",),
        ).fetchone()[0]

        result = maintain_checkpoint_db(
            db_path,
            thread_id="checkpoint-integrity",
            keep=3,
            vacuum=False,
        )
        assert result["removed"] == 0

        after = await agent.aget_state(config)
        _assert_tool_messages_are_paired(after.values["messages"])
        root_count_after = conn.execute(
            "SELECT count(*) FROM checkpoints "
            "WHERE thread_id=? AND checkpoint_ns=''",
            ("checkpoint-integrity",),
        ).fetchone()[0]
        assert root_count_after == root_count_before

        interrupt_id = collect_interrupt_groups(after)[0]["interruptId"]
        async for _ in agent.astream(
            Command(
                resume={
                    interrupt_id: {
                        "answers": [{"questionId": "q", "selected": ["yes"]}]
                    }
                }
            ),
            config=config,
            stream_mode="values",
        ):
            pass
        final = await agent.aget_state(config)
        _assert_tool_messages_are_paired(final.values["messages"])
        assert final.values["messages"][-1].content == "done"
    finally:
        conn.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


@pytest.mark.asyncio
async def test_dual_sqlite_saver_async_history_is_iterable():
    temp_dir = Path(tempfile.mkdtemp(prefix="checkpoint-history-"))
    conn = sqlite3.connect(str(temp_dir / "history.sqlite"), check_same_thread=False)
    saver = DualSqliteSaver(conn)
    saver.setup()
    try:
        # The async saver API must be an async iterator, matching LangGraph's
        # aget_state_history implementation.
        rows = [row async for row in saver.alist({"configurable": {"thread_id": "missing"}})]
        assert rows == []
    finally:
        conn.close()
        shutil.rmtree(temp_dir, ignore_errors=True)


def test_checkpoint_compactor_removes_only_explicitly_completed_child_namespace() -> None:
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    conn.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT, checkpoint BLOB, metadata BLOB)")
    conn.execute("CREATE TABLE writes (thread_id TEXT, checkpoint_ns TEXT, checkpoint_id TEXT)")
    conn.executemany(
        "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?)",
        [
            ("thread", "", "root", b"root", b'{\"status\":\"completed\"}'),
            ("thread", "tools:done", "child", b"done", b'{\"status\":\"completed\"}'),
            ("thread", "tools:waiting", "child2", b"interrupt", b'{\"status\":\"completed\"}'),
        ],
    )
    conn.executemany("INSERT INTO writes VALUES (?, ?, ?)", [("thread", "tools:done", "child"), ("thread", "tools:waiting", "child2")])

    assert compact_thread(conn, "thread") == 1
    assert conn.execute("SELECT count(*) FROM checkpoints WHERE checkpoint_ns='' ").fetchone()[0] == 1
    assert conn.execute("SELECT count(*) FROM checkpoints WHERE checkpoint_ns='tools:done'").fetchone()[0] == 0
    assert conn.execute("SELECT count(*) FROM checkpoints WHERE checkpoint_ns='tools:waiting'").fetchone()[0] == 1
