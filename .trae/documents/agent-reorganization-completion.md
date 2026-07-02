# 智能体代码重构 —— 完成阶段计划

## Summary（摘要）

本计划是已批准的 `agent-code-reorganization.md` 的**完成阶段**。前一阶段已成功创建 `agent_core/`、`tools/`、`sandbox/`、`artifacts/`、`entrypoints/web.py` 五个新模块并验证正确。本阶段聚焦于**剩余的收尾工作**：迁移其余 3 个入口（wechat/wecom/cli）、创建根级薄 shim、补全 `channels/` 三个空 `__init__.py`、更新两个 bridge 的 import 与产物检测、迁移测试脚本、删除根级旧文件、执行验证。

完成后根目录仅保留 4 个薄 shim 与文档，所有业务代码归入职责清晰的包结构，`agent_runtime.py`（1318 行）彻底删除，三套 agent 配置分歧统一收敛到 `agent_core.build_agent()`。

---

## Current State（现状：已完成 vs 待完成）

### 已完成（经验证正确，本阶段不再改动）
| 模块 | 文件 | 状态 |
|---|---|---|
| `agent_core/` | `config.py` / `llm.py` / `prompts.py` / `runtime.py` / `__init__.py` | ✅ 统一配置层 + `build_agent()` 工厂 + `agent` 单例 + 统一导出 |
| `tools/` | `web_search.py` / `render_html.py` / `get_current_time.py` / `__init__.py` | ✅ 扁平工具包，`render_html` 已用 `OUTPUT_DIR` |
| `sandbox/` | `constants.py` / `path_rewriter.py` / `backend.py` / `whitelist.py` / `__init__.py` | ✅ ~1200 行沙箱安全层拆分 + `backend` 单例组装 |
| `artifacts/` | `detector.py` / `__init__.py` | ✅ 两套快照/diff 函数（run.py 风格 + wechat 风格） |
| `entrypoints/web.py` | 676 行 | ✅ 从 `run.py` 迁移，含 `main()`，import 已改 `agent_core`/`artifacts` |

### 待完成（本阶段工作）
1. `entrypoints/wechat.py` / `wecom.py` / `cli.py` / `__init__.py` —— 4 个文件
2. 根级薄 shim：`run.py` / `run_wechat.py` / `run_wecom.py` / `demo.py` —— 4 个文件改写
3. `channels/__init__.py` / `wechat/__init__.py` / `wecom/__init__.py` —— 3 个空文件补内容
4. `channels/wechat/bridge.py` —— 改 import + 用 `artifacts` 模块
5. `channels/wecom/bridge.py` —— 改 import
6. `tests/test_playwright_pdf.py` —— 从根级迁入
7. 删除根级旧文件：`agent_runtime.py` / `ducktools.py` / `html_tools.py` / `time_tools.py` / `test_playwright_pdf.py`
8. 验证（静态检查 + import 冒烟测试）

---

## Proposed Changes（具体改动）

### 1. `entrypoints/wechat.py` ← 原 `run_wechat.py`
**What**：内容整体迁移，仅把 `async def main()` 改名为 `_async_main()`，新增同步 `main()` 包裹 `asyncio.run`。
**Why**：根级 shim 需调用同步 `main()`；原 `if __name__ == "__main__": asyncio.run(main())` 的语义由新 `main()` 承接。
**How**：
- 原 `async def main()`（L120）→ 重命名为 `async def _async_main()`
- 新增：
```python
def main() -> None:
    """个人微信渠道入口（根级 run_wechat.py shim 委派到此）。"""
    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        print("\n已退出")
```
- 其余内容（argparse 命令路由、`cmd_list`/`cmd_add`/`cmd_remove`/`run_single_account`/`run_accounts`、所有 `from channels.wechat.* import`）原样保留。
- 删除原 `if __name__ == "__main__":` 块（语义已并入 `main()`）。

### 2. `entrypoints/wecom.py` ← 原 `run_wecom.py`
**What**：内容原样迁移，已有同步 `def main()`，无需改造。
**Why**：`run_wecom.py` 已是 `def main()` + `if __name__ == "__main__": main()` 标准结构。
**How**：整体复制到 `entrypoints/wecom.py`，删除尾部 `if __name__ == "__main__": main()`（shim 自带），保留 `def main()` 与所有 import。

### 3. `entrypoints/cli.py` ← 原 `demo.py`（改动最大）
**What**：收敛到 `build_agent(hitl=True)`，消除短 prompt / 主 agent 含 web_search / `interrupt_on={"web_search":True}` 三项分叉，并用 `def main()` 包裹交互循环。
**Why**：落实 `AGENTS参考.md` L79「CLI 应收敛到 `create_deep_agent` 路径」，与 web/channel 行为一致。
**How**（按 demo.py 行号精确改动）：
- **删除** L1 `from deepagents import create_deep_agent`（已移入 `build_agent`）
- **删除** L9 `from langgraph.checkpoint.memory import MemorySaver`（已移入 `build_agent`）
- **删除** L16 `from agent_runtime import create_llm, backend, web_search, get_current_time`
- **新增** `from agent_core import build_agent`
- **保留** L2-8、L11-14：`os`/`logging`/`load_dotenv`/`langfuse.get_client`/`langfuse.langchain.CallbackHandler`/`uuid`/`AIMessageChunk,ToolMessage`/`Command`/`re`/`base64`/`mimetypes`/`urlopen`（交互循环与多模态逻辑仍用）
- **删除** L27 `llm = create_llm()`（不再需要，`build_agent` 内部调）
- **删除** L29 `system_prompt = "..."`（统一用 `SYSTEM_PROMPT`，由 `build_agent` 注入）
- **替换** L32-40 `agent = create_deep_agent(...)` → `agent = build_agent(hitl=True)`
- **保留** L31 `langfuse = get_client()`、L43-53 skill 启动检查、L55-58 `session_id`/`turn_count`/`langfuse_handler`/`_pending_tool_calls`、L61-90 `log_tool_call`、L93-116 多模态 `IMAGE_URL_RE`/`to_image_part`/`build_user_content`
- **包裹** L119-222 的 `while True:` 交互循环 + HITL 恢复循环整体放入 `def main():`，删除原顶层 `while True` 直接执行
- **行为变更**（统一装配的预期结果）：
  - 短 prompt → 完整 `SYSTEM_PROMPT`（含 output/tmp 约定）
  - 主 agent 工具 `[web_search, get_current_time]` → `[get_current_time, render_html]`（web_search 仅在 research_subagent，render_html 补齐）
  - `interrupt_on={"web_search":True,"execute":True}` → `{"execute":True}`（web_search 不在主 agent，原 web_search HITL 本就无效）
  - HITL 确认循环（L168-222）按 `all_action_requests` 通用遍历，不依赖具体工具名，故逻辑无需改动

### 4. `entrypoints/__init__.py`
**What**：包级文档字符串，无 eager import。
```python
"""入口实现包。

每个模块提供同步 main() 供根级薄 shim 委派：
- web:    FastAPI + SSE Web Bridge（原 run.py）
- wechat: 个人微信渠道（原 run_wechat.py）
- wecom:  企业微信渠道（原 run_wecom.py）
- cli:    交互式终端（原 demo.py，收敛到 build_agent）

根级 run.py / run_wechat.py / run_wecom.py / demo.py 仅 2-3 行 shim。
"""
```
**Why**：标识包身份，不 eager import 以避免导入 `entrypoints` 即触发 agent 构造。

### 5. 根级薄 shim（4 个，统一模式）
**What**：`run.py` / `run_wechat.py` / `run_wecom.py` / `demo.py` 各缩为 2-3 行。
**Why**：兼容现有启动命令（`python run.py` 等）。
**How**（统一模式）：
```python
# run.py
"""Agent Web Bridge 入口 shim。实际实现见 entrypoints/web.py。"""
from entrypoints.web import main

if __name__ == "__main__":
    main()
```
其余 3 个同理：`entrypoints.wechat.main` / `entrypoints.wecom.main` / `entrypoints.cli.main`。
**注意**：当前根级 `run.py`（762 行）、`demo.py`（223 行）等为旧完整实现，**整体覆盖**为 shim。

### 6. `channels/` 三个 `__init__.py` 补内容（当前均为 0 字节）
**What**：补文档字符串 + 轻量级 re-export，**不 eager import bridge**（避免导入即构造 agent）。
**Why**：包级文档清晰；避免 `channels/__init__` 触发 `agent_core.agent` 单例构建的副作用。
**How**：
- `channels/__init__.py`：
```python
"""多渠道接入包。

子包：
- channels.wechat: 个人微信渠道（ilink API，非流式）
- channels.wecom:  企业微信渠道（长连接，REPLACE 流式）

各渠道的 bridge 从 agent_core 导入 agent 单例；channel 专属配置
（WechatConfig/WeComConfig）保留在各自 config.py，不并入 agent_core.config。
"""
```
- `channels/wechat/__init__.py`：文档字符串 + `from channels.wechat.config import WechatConfig`（轻量，仅读环境变量，不触发 agent 构建）
- `channels/wecom/__init__.py`：文档字符串 + `from channels.wecom.config import WeComConfig`（同上）
**决策**：`Monitor`/`Sender`/`build_ws_client`/`handle_message` 等**不**在 `__init__` eager 导出——它们依赖较重的 SDK 或间接拉入 bridge（构造 agent）。调用方继续从子模块直接 import（与现状一致，如 `from channels.wechat.api import WeChatApi`）。这落实原计划「按需，避免循环」的注解。

### 7. `channels/wechat/bridge.py` 改造
**What**：import 改 `agent_core`；产物检测改用 `artifacts` 模块；移除本地 `_snapshot`/`_diff_artifacts`/`_WORKSPACE`/`_OUTPUT_DIR`。
**Why**：消除 `from agent_runtime import agent` 硬耦合；消除与 `run.py` 重复的产物检测逻辑。
**How**（按行号）：
- L28 `from pathlib import Path` → **删除**（改造后 Path 不再被使用）
- L31 `from agent_runtime import agent` → `from agent_core import agent`
- 新增 `from agent_core.config import OUTPUT_DIR`（仅当仍需 OUTPUT_DIR 引用——见下）和 `from artifacts import snapshot_output_dir_mtime, diff_changed_artifacts`
- L46-47 `_WORKSPACE = Path("workspace")` / `_OUTPUT_DIR = _WORKSPACE / "output"` → **删除**（`artifacts` 函数内部已用 `agent_core.config.OUTPUT_DIR`，bridge 不再需要本地变量）
- L65-91 `_snapshot()` / `_diff_artifacts()` → **删除**
- L250 `before = _snapshot(_OUTPUT_DIR)` → `before = snapshot_output_dir_mtime()`
- L263 `artifacts = _diff_artifacts(before, _snapshot(_OUTPUT_DIR))` → `artifacts = diff_changed_artifacts(before, snapshot_output_dir_mtime())`
- L270-271 `artifacts.sort(...)` 中 `p.stat().st_mtime` / `p.suffix` —— `diff_changed_artifacts` 返回 `list[Path]`，方法调用不变，**保留**
- L274 `sender.send_file(user_id, context_token, str(path))` —— `str(path)` 仍为 `workspace/output/xxx`，**保留**
**验证点**：`OUTPUT_DIR` 字面值不变（`Path("workspace")/"output"` == `agent_core.config.OUTPUT_DIR`），投递路径行为一致。

### 8. `channels/wecom/bridge.py` 改造
**What**：仅改一行 import。
**How**：L16 `from agent_runtime import agent` → `from agent_core import agent`。其余（`stream_agent_reply` 流式逻辑、`build_user_content` 多模态）原样保留。wecom 无产物检测逻辑。

### 9. `tests/test_playwright_pdf.py` ← 根级 `test_playwright_pdf.py`
**What**：文件移动，无内容改动。
**Why**：测试与生产代码分离。
**How**：原样复制到 `tests/test_playwright_pdf.py`，新建 `tests/__init__.py`（空文件标识包，或仅文档字符串）。该脚本无项目内 import（经核实，仅依赖 `playwright` + 标准库），`Path(__file__).parent / "output"` 迁移后输出到 `tests/output`，对独立测试脚本可接受。
**新增** `tests/__init__.py`：
```python
"""测试包。"""
```

### 10. 删除根级旧文件
**前置条件**：步骤 1-9 全部完成，且静态检查（验证步骤 1-2）确认无残留旧 import。
**删除**：
- `agent_runtime.py`（内容已拆分到 `agent_core/` + `sandbox/`）
- `ducktools.py`（已移入 `tools/web_search.py`）
- `html_tools.py`（已移入 `tools/render_html.py`）
- `time_tools.py`（已移入 `tools/get_current_time.py`）
- `test_playwright_pdf.py`（已移入 `tests/`）

---

## Execution Order（执行顺序）

按依赖关系串行+并行结合，避免中间态 import 断裂：

1. **创建 entrypoints 剩余文件**（步骤 1-4）：`wechat.py`、`wecom.py`、`cli.py`、`__init__.py`
2. **改写根级 4 个 shim**（步骤 5）：`run.py`、`run_wechat.py`、`run_wecom.py`、`demo.py` → 此时根级旧实现被覆盖
3. **更新 channels**（步骤 6-8）：3 个 `__init__.py` + 2 个 `bridge.py`
4. **迁移测试**（步骤 9）：`tests/test_playwright_pdf.py` + `tests/__init__.py`
5. **静态检查**（验证步骤 1-3）：grep 确认无 `from agent_runtime` / `from ducktools` / `from html_tools` / `from time_tools` 残留
6. **删除根级旧文件**（步骤 10）
7. **导入冒烟测试**（验证步骤 4-9）
8. **入口冒烟测试**（验证步骤 10-13）

---

## Assumptions & Decisions（假设与决策）

1. **决策**：`entrypoints/wechat.py` 把原 `async def main()` 改名 `_async_main()`，新增同步 `main()` 包 `asyncio.run`——因 shim 调用的是同步 `main()`。
2. **决策**：`entrypoints/cli.py` 的 skill 启动检查块（demo.py L43-53）原样保留——属无害启动诊断，不在「agent 构造」或「交互循环」范畴，保留以最小化改动。
3. **决策**：`channels/*/` 三个 `__init__.py` 仅 re-export 轻量 config 类（`WechatConfig`/`WeComConfig`），**不** eager 导出 `Monitor`/`Sender`/`handle_message`/`build_ws_client`——避免导入 `channels` 包即触发 `agent_core.agent` 单例构建或 SDK 初始化的副作用。落实原计划「按需，避免循环」注解。
4. **决策**：`channels/wechat/bridge.py` 改造后移除 `from pathlib import Path`（改造后 Path 不再被使用，避免未使用 import）。
5. **假设**：`agent_core.config.OUTPUT_DIR`（`Path("workspace")/"output"`）与原 `_OUTPUT_DIR`（`Path("workspace")/"output"`）字面值相同，wechat 产物投递路径行为不变。
6. **假设**：`entrypoints/cli.py` 模块级 `agent = build_agent(hitl=True)` 在 shim `from entrypoints.cli import main` 时即触发 agent 构造——与原 `demo.py` 模块级构造行为一致，无回归。
7. **假设**：`tests/test_playwright_pdf.py` 无项目内 import，移动后 `Path(__file__).parent/"output"` 指向 `tests/output`，对独立测试可接受。

---

## Verification Steps（验证步骤）

### 阶段 1：静态检查
1. **包结构完整性**：确认 `entrypoints/`（含 `__init__.py`）、`tests/`（含 `__init__.py`）存在。
2. **无残留旧 import**：`grep -rn "from agent_runtime import\|from ducktools import\|from html_tools import\|from time_tools import\|import agent_runtime\|import ducktools\|import html_tools\|import time_tools" /workspace --include="*.py" -l` 应仅命中将被删除的根级旧文件（或为空）。
3. **旧文件已删**：`ls /workspace/agent_runtime.py /workspace/ducktools.py /workspace/html_tools.py /workspace/time_tools.py /workspace/test_playwright_pdf.py` 全部报「不存在」。

### 阶段 2：导入冒烟测试
4. `cd /workspace && python -c "import agent_core; print(agent_core.agent is not None)"` — agent 单例可构造。
5. `cd /workspace && python -c "from tools import web_search, render_html, get_current_time; print('tools ok')"`
6. `cd /workspace && python -c "from sandbox import backend; print('sandbox ok')"`
7. `cd /workspace && python -c "from artifacts import snapshot_output_dir, detect_new_artifacts, snapshot_output_dir_mtime, diff_changed_artifacts; print('artifacts ok')"`
8. `cd /workspace && python -c "from channels.wechat.bridge import handle_message; print('wechat ok')"` — 不再因 `agent_runtime` 缺失失败。
9. `cd /workspace && python -c "from channels.wecom.bridge import stream_agent_reply; print('wecom ok')"` — 同上。

### 阶段 3：入口冒烟测试
10. `cd /workspace && python -c "from entrypoints.web import main; print('web entry ok')"` — web 入口可加载（不启动 uvicorn）。
11. `cd /workspace && python -c "from entrypoints.cli import main; print('cli entry ok')"` — CLI 入口可加载。
12. `cd /workspace && python -c "from entrypoints.wechat import main; print('wechat entry ok')"`
13. `cd /workspace && python -c "from entrypoints.wecom import main; print('wecom entry ok')"`

### 阶段 4：清理验证
14. **根目录 Python 文件**：`ls /workspace/*.py` 输出仅 4 个 shim（`run.py`、`run_wechat.py`、`run_wecom.py`、`demo.py`），无 `agent_runtime.py`/`ducktools.py`/`html_tools.py`/`time_tools.py`/`test_playwright_pdf.py`。
15. **shim 行数**：4 个 shim 各 2-4 行（docstring + 1 import + `if __name__` 块）。

### 阶段 5：行为一致性（可选，需运行时环境）
16. **agent 配置统一**：`python -c "from agent_core import build_agent; a=build_agent(hitl=False); b=build_agent(hitl=True); print('both ok')"`
17. **产物检测去重**：确认 `entrypoints/web.py` 用 `artifacts.detect_new_artifacts`，`channels/wechat/bridge.py` 用 `artifacts.diff_changed_artifacts`，无各自本地实现。
18. **前端契约不变**：启动 `python run.py`，curl `/health` 返回 `{"ok":true,...}`（需 LLM env 就绪）。
