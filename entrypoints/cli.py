"""交互式 / 无头 CLI 入口。

用法：
    python -m entrypoints.cli
    python -m entrypoints.cli --mode plan
    python -m entrypoints.cli --format streaming-json -p "解释本仓库"
    python -m entrypoints.cli --always-approve -p "列出 skills"
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import uuid

from dotenv import load_dotenv
from langchain_core.messages import AIMessageChunk, ToolMessage
from langgraph.types import Command

from agent_core import build_agent
from agent_core.config import LANGFUSE_ENABLED
from agent_core.events import SCHEMA_VERSION, make_event
from agent_core.multimodal import build_user_content, to_image_part
from agent_core.permissions import AgentMode
from agent_core.stream_emit import emit_ndjson

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logging.getLogger("deepagents").setLevel(logging.DEBUG)

IMAGE_URL_RE = re.compile(
    r"https?://[^\s]+\.(?:jpg|jpeg|png|gif|webp|bmp)(?:\?[^\s]*)?",
    re.IGNORECASE,
)

_pending_tool_calls: dict = {}


def log_tool_call(msg_chunk, *, json_mode: bool = False) -> None:
    tool_calls = getattr(msg_chunk, "tool_call_chunks", None) or []
    for tc in tool_calls:
        idx = tc.get("index", 0)
        if idx not in _pending_tool_calls:
            _pending_tool_calls[idx] = {
                "name": "", "args": "", "id": "", "start_emitted": False,
            }
        if tc.get("name"):
            _pending_tool_calls[idx]["name"] += tc["name"]
        if tc.get("args"):
            _pending_tool_calls[idx]["args"] += tc["args"]
        if tc.get("id"):
            _pending_tool_calls[idx]["id"] = tc["id"]

    if not isinstance(msg_chunk, ToolMessage):
        if json_mode:
            for tc in _pending_tool_calls.values():
                if tc["name"] and not tc["start_emitted"]:
                    emit_ndjson(make_event(
                        "tool_call",
                        callId=tc.get("id") or f"tc_{uuid.uuid4().hex[:8]}",
                        name=tc["name"],
                        # Arguments may still be streaming and can contain
                        # sensitive prompts. The completion event carries only
                        # a bounded result preview.
                        args="",
                    ))
                    tc["start_emitted"] = True
        return

    name = msg_chunk.name or ""
    content_preview = str(msg_chunk.content)[:300]
    args_str = ""
    call_id = getattr(msg_chunk, "tool_call_id", "") or ""
    for tc in _pending_tool_calls.values():
        if tc["name"] == name:
            args_str = tc["args"]
            call_id = call_id or tc.get("id") or call_id
            break

    denied = "[E_PERMISSION_DENIED]" in str(msg_chunk.content) or "[E_SHELL_DENIED]" in str(
        msg_chunk.content
    )
    if json_mode:
        matched = next(
            (tc for tc in _pending_tool_calls.values() if tc["name"] == name), None
        )
        if not matched or not matched.get("start_emitted"):
            emit_ndjson(make_event(
                "tool_call",
                callId=call_id or f"tc_{uuid.uuid4().hex[:8]}",
                name=name,
                args="",
            ))
        emit_ndjson(
            make_event(
                "tool_result",
                callId=call_id or f"tc_{uuid.uuid4().hex[:8]}",
                name=name,
                output=content_preview,
                denied=denied,
            )
        )
    else:
        if name == "read_file" and "SKILL.md" in args_str:
            print(f"\n🔧 [SKILL 激活] {name}({args_str})", flush=True)
        else:
            print(f"\n🛠️ [工具调用] {name}({args_str})", flush=True)
        print(
            f"📋 [工具结果] {content_preview}"
            f"{'...' if len(str(msg_chunk.content)) > 300 else ''}",
            flush=True,
        )


def _print_skill_check() -> None:
    skills_dir = os.path.join("workspace", "skills")
    print(f"\n[SKILL 检查] skills 目录: {os.path.abspath(skills_dir)}")
    if os.path.isdir(skills_dir):
        for name in os.listdir(skills_dir):
            skill_md = os.path.join(skills_dir, name, "SKILL.md")
            status = "✅ 找到" if os.path.isfile(skill_md) else "❌ 缺失"
            print(f"  - {name}: {status} SKILL.md")
    else:
        print(f"  ❌ 目录不存在: {skills_dir}")
    print()


def _hitl_loop(agent, config: dict, *, json_mode: bool, always_approve: bool) -> None:
    from tools.ask_user_question import ASK_USER_KIND, collect_interrupt_groups

    while True:
        state = agent.get_state(config)
        if not state.next:
            break

        groups = collect_interrupt_groups(state)
        if not groups:
            break

        if json_mode:
            emit_ndjson(make_event("interrupt", groups=groups))

        resume_map: dict = {}
        for grp in groups:
            kind = grp.get("kind")
            iid = grp["interruptId"]
            if kind == ASK_USER_KIND:
                questions = grp.get("questions") or []
                title = grp.get("title") or "需要你的确认"
                if always_approve or json_mode:
                    answers = []
                    for q in questions:
                        opts = q.get("options") or []
                        selected = [opts[0]] if opts else ["确认继续"]
                        answers.append(
                            {"questionId": q.get("id"), "selected": selected, "text": ""}
                        )
                    if json_mode and not always_approve:
                        print(
                            f"[ASK] auto-answer in streaming-json: {title}",
                            file=sys.stderr,
                        )
                    resume_map[iid] = {"answers": answers}
                    continue

                print(f"\n❓ {title}")
                answers = []
                for q in questions:
                    qid = q.get("id")
                    prompt = q.get("prompt") or ""
                    opts = q.get("options") or []
                    allow_multi = bool(q.get("allowMultiple"))
                    allow_free = bool(q.get("allowFreeText", True))
                    print(f"\n  [{qid}] {prompt}")
                    selected: list[str] = []
                    if opts:
                        for i, o in enumerate(opts, 1):
                            print(f"    {i}. {o}")
                        hint = "可多选，逗号分隔编号" if allow_multi else "输入编号"
                        raw = input(f"    选择（{hint}，回车跳过）: ").strip()
                        if raw:
                            for part in raw.split(","):
                                part = part.strip()
                                if part.isdigit():
                                    idx = int(part) - 1
                                    if 0 <= idx < len(opts):
                                        selected.append(opts[idx])
                    text = ""
                    if allow_free:
                        text = input("    补充说明（可空）: ").strip()
                    if not selected and not text and opts:
                        selected = [opts[0]]
                    if not selected and not text:
                        selected = ["确认继续"]
                    answers.append({"questionId": qid, "selected": selected, "text": text})
                resume_map[iid] = {"answers": answers}
                continue

            # tool_approval
            action_requests = grp.get("toolCalls") or []
            grp_decisions = []
            total = len(action_requests)
            for flat_idx, req in enumerate(action_requests, 1):
                tool_name = req.get("name", "未知工具")
                tool_args = req.get("args", {})
                if always_approve:
                    grp_decisions.append({"type": "approve"})
                    continue
                if json_mode:
                    print(
                        f"[HITL] auto-reject in streaming-json without --always-approve: {tool_name}",
                        file=sys.stderr,
                    )
                    grp_decisions.append({"type": "reject"})
                    continue
                print(f"\n⚠️ [{flat_idx}/{total}] 需要确认：是否允许调用 [{tool_name}]？")
                print(f"   参数: {tool_args}")
                user_decision = input("   输入 y 批准 / n 拒绝: ").strip().lower()
                if user_decision == "y":
                    print("   ✅ 已批准")
                    grp_decisions.append({"type": "approve"})
                else:
                    print("   ❌ 已拒绝")
                    grp_decisions.append({"type": "reject"})
            resume_map[iid] = {"decisions": grp_decisions}

        need_prefix = True
        _pending_tool_calls.clear()
        try:
            for msg_chunk, _meta in agent.stream(
                Command(resume=resume_map),
                config=config,
                stream_mode="messages",
            ):
                log_tool_call(msg_chunk, json_mode=json_mode)
                if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                    text = msg_chunk.content
                    if isinstance(text, list):
                        text = "".join(
                            p.get("text", "")
                            for p in text
                            if isinstance(p, dict) and p.get("type") == "text"
                        )
                    if not text:
                        continue
                    if json_mode:
                        emit_ndjson(make_event("delta", delta=str(text)))
                    else:
                        print(
                            f"{'小权: ' if need_prefix else ''}{text}",
                            end="",
                            flush=True,
                        )
                        need_prefix = False
            if not json_mode:
                print()
        except Exception as e:  # noqa: BLE001
            if json_mode:
                emit_ndjson(make_event("error", message=f"{type(e).__name__}: {e}"))
            else:
                print(f"\n⚠️ 恢复执行异常: {type(e).__name__}: {e}")

        if not agent.get_state(config).next:
            break


def run_once(
    agent,
    user_input: str,
    *,
    session_id: str,
    turn: int,
    json_mode: bool,
    always_approve: bool,
    max_turns: int | None,
) -> None:
    if max_turns is not None and turn > max_turns:
        if json_mode:
            emit_ndjson(make_event("error", message=f"exceeded max-turns={max_turns}"))
            emit_ndjson(make_event("done", messageId=f"turn-{turn}"))
        else:
            print(f"⚠️ 已达 --max-turns={max_turns}")
        return

    message_id = str(uuid.uuid4())
    if json_mode:
        emit_ndjson(make_event("start", messageId=message_id))

    config = {
        "configurable": {"thread_id": session_id},
        "run_name": f"turn{turn}: {user_input[:20]}{'…' if len(user_input) > 20 else ''}",
    }

    image_urls = IMAGE_URL_RE.findall(user_input)
    text = IMAGE_URL_RE.sub("", user_input).strip() or "请描述这张图"
    try:
        user_content = build_user_content(text, image_urls)
    except Exception as e:  # noqa: BLE001
        if json_mode:
            emit_ndjson(make_event("error", message=f"load image failed: {e}"))
        else:
            print(f"\n⚠️ 加载图片失败: {e}")
        user_content = text

    need_prefix = True
    _pending_tool_calls.clear()
    try:
        for msg_chunk, _meta in agent.stream(
            {"messages": [{"role": "user", "content": user_content}]},
            stream_mode="messages",
            config=config,
        ):
            log_tool_call(msg_chunk, json_mode=json_mode)
            if isinstance(msg_chunk, AIMessageChunk) and msg_chunk.content:
                content = msg_chunk.content
                if isinstance(content, list):
                    content = "".join(
                        p.get("text", "")
                        for p in content
                        if isinstance(p, dict) and p.get("type") == "text"
                    )
                if not content:
                    continue
                if json_mode:
                    emit_ndjson(make_event("delta", delta=str(content)))
                else:
                    print(f"{'小权: ' if need_prefix else ''}{content}", end="", flush=True)
                    need_prefix = False
        if not json_mode:
            print()
    except Exception as e:  # noqa: BLE001
        if json_mode:
            emit_ndjson(make_event("error", message=f"{type(e).__name__}: {e}"))
        else:
            print(f"\n⚠️ 异常: {type(e).__name__}: {e}")

    _hitl_loop(agent, config, json_mode=json_mode, always_approve=always_approve)

    if json_mode:
        emit_ndjson(make_event("done", messageId=message_id))


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="DeepAgent CLI")
    p.add_argument("-p", "--prompt", help="单次提示（无头）；省略则进入交互循环")
    p.add_argument(
        "--format",
        choices=("text", "streaming-json"),
        default="text",
        help="输出格式：text（默认）或 streaming-json（NDJSON）",
    )
    p.add_argument(
        "--mode",
        choices=("agent", "plan"),
        default=None,
        help="agent（默认可执行）或 plan（只规划）",
    )
    p.add_argument(
        "--always-approve",
        action="store_true",
        help="自动批准所有 HITL（ask→allow）",
    )
    p.add_argument("--max-turns", type=int, default=None, help="最大轮次（含交互）")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    mode: AgentMode = args.mode or (
        "plan" if os.getenv("AGENT_MODE", "").lower() == "plan" else "agent"
    )
    json_mode = args.format == "streaming-json"
    # 仅显式 --always-approve 升权；输出格式不得改变安全策略
    always_approve = bool(args.always_approve)
    hitl = not always_approve

    agent = build_agent(
        hitl=hitl,
        mode=mode,
        entrypoint="cli",
        always_approve=always_approve,
    )

    if not json_mode:
        _print_skill_check()
        print(f"[CLI] mode={mode} hitl={hitl} schemaVersion={SCHEMA_VERSION}")

    if LANGFUSE_ENABLED:
        try:
            from langfuse import get_client
            from langfuse.langchain import CallbackHandler

            get_client()
            _ = CallbackHandler  # 可选；交互路径不强依赖
        except Exception:  # noqa: BLE001
            pass

    session_id = str(uuid.uuid4())

    if args.prompt is not None:
        run_once(
            agent,
            args.prompt,
            session_id=session_id,
            turn=1,
            json_mode=json_mode,
            always_approve=always_approve,
            max_turns=args.max_turns,
        )
        return

    if json_mode:
        print(
            "streaming-json 交互模式请用 -p；或省略 --format 进入文本交互",
            file=sys.stderr,
        )
        sys.exit(2)

    turn = 0
    while True:
        user_input = input("\n👤 你: ")
        if user_input.lower() == "exit":
            print("小权: 再见！")
            break
        turn += 1
        if args.max_turns is not None and turn > args.max_turns:
            print(f"⚠️ 已达 --max-turns={args.max_turns}")
            break
        run_once(
            agent,
            user_input,
            session_id=session_id,
            turn=turn,
            json_mode=False,
            always_approve=always_approve,
            max_turns=None,
        )


if __name__ == "__main__":
    main()
