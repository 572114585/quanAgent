# 智能体代码目录结构重构计划

## Summary（摘要）

将 `/workspace` 根目录下扁平散落的运行时、工具、入口脚本重组为职责清晰的 Python 包结构，消除 `agent_runtime.py`（1318 行）的职责过载、三套 agent 配置分歧、产物检测逻辑重复、配置分散等问题。重构后根目录只保留薄入口 shim 和文档，业务代码归入 `agent_core/`、`sandbox/`、`tools/`、`entrypoints/`、`artifacts/`、`channels/`（补全）等包，行为对外保持一致（前端契约、启动命令不变）。

**范围**：全面重构（目录整理 + 统一 agent 装配 + 提取 sandbox 独立模块 + 统一配置层 + 消除产物检测重复）。
**不动**：`agent-frontend/`（网络解耦，端点契约不变）、`workspace/skills/`（运行时数据）、所有 `.md` 文档、`requirement.txt`。

---

## Current State Analysis（现状分析）

### 问题 1：根目录扁平化，无包结构
`/workspace/__init__.py` 不存在。`agent_runtime.py`、`ducktools.py`、`html_tools.py`、`time_tools.py`、`run.py`、`run_wechat.py`、`run_wecom.py`、`demo.py`、`test_playwright_pdf.py` 9 个 Python 文件全堆在根，靠 `cwd=项目根` 才能 import，无法作为包复用。

### 问题 2：`agent_runtime.py` 职责严重过载（1318 行）
一个文件混合 4 类不相关逻辑：
- L39–1238（~1200 行）：Shell 沙箱安全层（`_SkillsShellBackend`@L719 + `_ShellWhitelistFilter`@L1041 + 28 个 shlex/路径改写辅助函数 + 2 个白名单常量）
- L1240–1258：`create_llm()` 工厂 + `llm` 单例
- L1260–1290：`SYSTEM_PROMPT` + `research_subagent` 定义
- L1292–1318：模块级 `agent` 单例装配 + `new_thread_id()`

### 问题 3：三套 agent 配置分歧
| 入口 | system_prompt | tools | interrupt_on | 来源 |
|---|---|---|---|---|
| `agent_runtime.py` 单例 (L1306) | 完整 SYSTEM_PROMPT | `[get_current_time, render_html]` | 无 | 模块级 |
| `run.py` build_agent (L120) | 复用 SYSTEM_PROMPT | `[get_current_time, render_html]` | None | 自建 |
| `demo.py` (L32) | **短 prompt**（L29） | `[web_search, get_current_time]`（含 web_search、缺 render_html） | `{"web_search":True,"execute":True}` | 自建 |

`AGENTS参考.md` L79 明确要求"CLI 应收敛到 `create_deep_agent` 路径"，`demo.py` 违反此约定。且 `web_search` 已下放给 `research_subagent`，`demo.py` 把它放主 agent 是历史遗留分叉；`interrupt_on={"web_search":True}` 对主 agent 实际无效（web_search 不在主 agent 工具集，统一后也不在）。

### 问题 4：工具导入路径不一致
- `run.py` L70 从 `agent_runtime` 导入 `render_html`，L73 却从 `time_tools` 直接导入 `get_current_time`
- `demo.py` L16 从 `agent_runtime` 导入 `web_search`/`get_current_time`（靠 re-export，但单例根本没注册 web_search）
- 同类工具三种导入习惯

### 问题 5：产物检测逻辑重复
- `run.py` L182–232：`_snapshot_output_dir()` / `_detect_new_artifacts()`（含 16 项 mime_map）
- `channels/wechat/bridge.py` L65–91：`_snapshot()` / `_diff_artifacts()`
- 两份实现做相同的事（对比 output/ 前后快照），各自维护

### 问题 6：配置分散三处 + "workspace" 魔法字符串
- `agent_runtime.py` L1242：`os.getenv("LLM_PROVIDER")`
- `channels/wechat/config.py`：`WechatConfig.from_env()`
- `channels/wecom/config.py`：`WeComConfig.from_env()`
- `run.py` L93/96：`HITL_ENABLED` / `MAX_UPLOAD_SIZE`
- `"workspace"` 硬编码散落 4 处：`agent_runtime.py` L1293/1294/1297、`html_tools.py` L59/123/171、`run.py` L174/175、`channels/wechat/bridge.py` L46

### 问题 7：`channels/__init__.py` 全空 + bridge 硬耦合单例
`channels/__init__.py`、`channels/wechat/__init__.py`、`channels/wecom/__init__.py` 均 0 字节。`channels/wechat/bridge.py` L31 和 `channels/wecom/bridge.py` L16 都 `from agent_runtime import agent`——模块导入即触发单例构造，channel 与 runtime 强耦合。

### 问题 8：测试脚本混在根目录
`test_playwright_pdf.py` 是测试却在根目录，不在 `tests/`。

---

## Target Directory Structure（目标目录结构）

```
/workspace/
├── agent_core/                      # 【新建】agent 核心装配包（替代根级 agent_runtime.py 的非沙箱部分）
│   ├── __init__.py                  # 统一导出: agent, build_agent, create_llm, SYSTEM_PROMPT, research_subagent, new_thread_id
│   ├── config.py                    # 统一配置层: 路径常量 + LLM/HITL/上传开关
│   ├── llm.py                       # create_llm() + llm 单例
│   ├── prompts.py                   # SYSTEM_PROMPT + research_subagent 定义
│   └── runtime.py                   # build_agent() 工厂 + agent 模块单例 + new_thread_id()
├── sandbox/                         # 【新建】从 agent_runtime.py 拆出的 ~1200 行沙箱安全层
│   ├── __init__.py                  # 统一导出: backend, _SkillsShellBackend, _ShellWhitelistFilter
│   ├── constants.py                 # DEFAULT_ALLOWED_COMMANDS, _NODE_BUILD_COMMANDS
│   ├── path_rewriter.py             # shlex 分词 + token 级路径改写函数（_split_into_segments 等 ~20 个辅助函数）
│   ├── backend.py                   # _SkillsShellBackend（内层：路径改写 + 编码兼容）
│   └── whitelist.py                 # _ShellWhitelistFilter（外层：命令白名单）+ 组装 backend 单例
├── tools/                           # 【新建】扁平工具包
│   ├── __init__.py                  # 统一导出: web_search, render_html, get_current_time
│   ├── web_search.py                # 原 ducktools.py（@tool web_search）
│   ├── render_html.py               # 原 html_tools.py（@tool render_html）
│   └── get_current_time.py          # 原 time_tools.py（@tool get_current_time）
├── artifacts/                       # 【新建】产物检测统一模块（消除 run.py 与 wechat bridge 重复）
│   ├── __init__.py                  # 导出 snapshot_output_dir, detect_new_artifacts
│   └── detector.py                  # snapshot_output_dir() / detect_new_artifacts()（合并两份实现）
├── channels/                        # 【保留，补全 __init__.py 导出 + 改 import】
│   ├── __init__.py                  # 补包级导出 + 文档字符串
│   ├── wechat/
│   │   ├── __init__.py              # 补包级导出
│   │   ├── bridge.py                # 改: from agent_core import agent；产物检测改用 artifacts 模块
│   │   └── ... (accounts/api/commands/config/crypto/login/media/... 不动)
│   └── wecom/
│       ├── __init__.py              # 补包级导出
│       ├── bridge.py                # 改: from agent_core import agent
│       └── ... (client/config/handlers 不动)
├── entrypoints/                     # 【新建】实际入口实现
│   ├── __init__.py
│   ├── web.py                       # 原 run.py 主体（FastAPI + SSE）
│   ├── wechat.py                    # 原 run_wechat.py 主体
│   ├── wecom.py                     # 原 run_wecom.py 主体
│   └── cli.py                       # 原 demo.py 主体（收敛到 build_agent，消除配置分叉）
├── tests/                           # 【新建】测试归位
│   └── test_playwright_pdf.py       # 原根级 test_playwright_pdf.py
├── run.py                           # 【薄 shim】from entrypoints.web import main; main()
├── run_wechat.py                    # 【薄 shim】
├── run_wecom.py                     # 【薄 shim】
├── demo.py                          # 【薄 shim】
├── workspace/                       # 运行时数据目录（不动）
│   └── skills/
├── agent-frontend/                  # 前端（不动）
├── requirement.txt                  # 不动
├── README.md / README_ARCHITECTURE.md / AGENTS参考.md / deepagent指南.md / 项目记录  # 不动
└── .gitignore
```

**删除**：原 `agent_runtime.py`（内容拆分到 `agent_core/` + `sandbox/`，所有 import 更新到新路径，不留 re-export shim）。
**删除**：原 `ducktools.py` / `html_tools.py` / `time_tools.py`（移入 `tools/` 后删除根级原件）。
**删除**：原 `test_playwright_pdf.py`（移入 `tests/`）。

---

## Proposed Changes（具体改动）

### 1. 新建 `agent_core/config.py` — 统一配置层
**What**：集中所有跨模块共享的路径常量与运行时开关。
**Why**：消除 "workspace" 魔法字符串散落 4 处、配置分散 3 处的问题。
**How**：
```python
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(os.getenv("WORKSPACE_ROOT", "workspace"))  # 保持 "workspace" 字面值
OUTPUT_DIR = WORKSPACE_ROOT / "output"
TMP_DIR = WORKSPACE_ROOT / "tmp"
SKILLS_DIR = WORKSPACE_ROOT / "skills"
UPLOADS_DIR = WORKSPACE_ROOT / "uploads"

HITL_ENABLED_DEFAULT = os.getenv("HITL_ENABLED", "true").lower() in ("1", "true", "yes")
MAX_UPLOAD_SIZE = int(os.getenv("MAX_UPLOAD_SIZE", str(20 * 1024 * 1024)))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

def ensure_runtime_dirs() -> None:
    """启动时确保 workspace/tmp、workspace/output 存在。"""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
```
**注意**：`skills=["skills/"]` 这个传给 `create_deep_agent` 的字面量**保持不变**（其解析语义涉及 deepagents 内部，不在本次重构范围内）。

### 2. 新建 `agent_core/llm.py` — LLM 工厂
**What**：迁移 `agent_runtime.py` L1240–1258 的 `create_llm()` + `llm` 单例。
**Why**：与沙箱、prompt 解耦，独立可测。
**How**：原样迁移 `create_llm()` 函数体（读 `LLM_PROVIDER`/`AGNES_*`/`DEEPSEEK_*`），保留模块级 `llm = create_llm()` 单例。

### 3. 新建 `agent_core/prompts.py` — 提示词与子 agent 定义
**What**：迁移 `agent_runtime.py` L1260–1290 的 `SYSTEM_PROMPT` + `research_subagent`。
**Why**：prompt 与 agent 装配分离，便于独立维护。
**How**：原样迁移。`research_subagent` 的 `tools=[web_search]` 改为 `from tools import web_search`。

### 4. 新建 `agent_core/runtime.py` — 统一 agent 装配入口
**What**：提供**唯一**的 `build_agent()` 工厂 + 模块级 `agent` 单例 + `new_thread_id()`，消除三套配置分歧。
**Why**：解决 demo.py/run.py/单例三分叉，落实 `AGENTS参考.md` L79 "CLI 收敛到 create_deep_agent" 约定。
**How**：
```python
from deepagents import create_deep_agent
from langgraph.checkpoint.memory import MemorySaver
from agent_core.llm import create_llm
from agent_core.prompts import SYSTEM_PROMPT, research_subagent
from agent_core.config import ensure_runtime_dirs
from sandbox import backend
from tools import get_current_time, render_html
import uuid

def build_agent(*, hitl: bool = False):
    """统一 agent 装配入口。所有入口（web/cli/channel）必须经此构造。"""
    ensure_runtime_dirs()
    interrupt_on = {"execute": True} if hitl else None
    return create_deep_agent(
        model=create_llm(),
        system_prompt=SYSTEM_PROMPT,
        backend=backend,
        tools=[get_current_time, render_html],
        subagents=[research_subagent],
        interrupt_on=interrupt_on,
        checkpointer=MemorySaver(),
        skills=["skills/"],
    )

# 模块级单例：供 channels 直接 import（无 HITL，与原 agent_runtime.agent 行为一致）
agent = build_agent(hitl=False)

def new_thread_id(prefix: str = "thread") -> str:
    return f"{prefix}:{uuid.uuid4()}"
```
**行为变更说明**（需在验证阶段确认）：
- `demo.py` 原本的短 prompt → 统一为完整 `SYSTEM_PROMPT`（含 output/tmp 约定）。
- `demo.py` 原本主 agent 含 `web_search` → 统一移除（web_search 仅在 research_subagent 内，与 runtime 设计一致）。
- `demo.py` 原本 `interrupt_on={"web_search":True,"execute":True}` → 统一为 `{"execute":True}`（web_search 不在主 agent，原 web_search HITL 本就无效）。
- 这些变更是"统一装配"的预期结果，使 CLI 与 web/channel 行为一致。

### 5. 新建 `agent_core/__init__.py` — 统一导出
```python
from agent_core.runtime import agent, build_agent, new_thread_id
from agent_core.llm import create_llm, llm
from agent_core.prompts import SYSTEM_PROMPT, research_subagent
from agent_core.config import (
    WORKSPACE_ROOT, OUTPUT_DIR, TMP_DIR, SKILLS_DIR, UPLOADS_DIR,
    HITL_ENABLED_DEFAULT, MAX_UPLOAD_SIZE, LOG_LEVEL, ensure_runtime_dirs,
)
```

### 6. 新建 `sandbox/` 包 — 拆出 ~1200 行沙箱安全层
**What**：将 `agent_runtime.py` L39–1238 的沙箱代码拆为 4 个文件。
**Why**：安全关键代码独立成模块，`agent_runtime` 不再过载，沙箱可独立测试。
**How**（按 L39–1238 的逻辑边界拆分）：
- `sandbox/constants.py`：`DEFAULT_ALLOWED_COMMANDS`(L66)、`_NODE_BUILD_COMMANDS`(L121)
- `sandbox/path_rewriter.py`：所有 shlex/路径改写辅助函数（L158–L718 的 `_split_into_segments`/`_split_segment_tokens`/`_extract_command_head`/`_extract_python_positional`/`_extract_bash_positional`/`_extract_curl_urls`/`_curl_urls_allowed`/`_build_default_allow_pattern`/`_discover_skill_scripts`/`_is_absolute_path`/`_is_url`/`_to_posix`/`_rewrite_path_token`/`_tokenize_with_positions`/`_normalize_command_paths`/`_path_under_subdir`/`_decode_shell_output`/`_build_skill_subprocess_env` + L949–L1039 的 `_is_virtual_posix_path`/`_path_stays_within_root`/`_build_rejection_response`）
- `sandbox/backend.py`：`_SkillsShellBackend` 类（L719–948）
- `sandbox/whitelist.py`：`_ShellWhitelistFilter` 类（L1041–1238）+ 模块级 `backend` 单例组装（原 L1296–1302，`_inner_backend` → `_ShellWhitelistFilter(...)`）
- `sandbox/__init__.py`：`from sandbox.whitelist import backend`；按需导出两个类
**注意**：`_discover_skill_scripts` 的 glob 路径、`_SkillsShellBackend(root_dir="workspace")` 改为 `root_dir=str(WORKSPACE_ROOT)`（保持 "workspace" 字面值）。

### 7. 新建 `tools/` 包 — 扁平工具包
**What**：3 个工具模块移入 `tools/` 并重命名。
**Why**：工具不再散落根目录，统一导出入口。
**How**：
- `tools/web_search.py` ← 原 `ducktools.py`（内容不变）
- `tools/render_html.py` ← 原 `html_tools.py`（内部 `Path("workspace")` 改为 `from agent_core.config import OUTPUT_DIR`，保持路径值 "workspace/output" 不变）
- `tools/get_current_time.py` ← 原 `time_tools.py`（内容不变）
- `tools/__init__.py`：`from tools.web_search import web_search; from tools.render_html import render_html; from tools.get_current_time import get_current_time`
**注意**：`tools/render_html.py` import `agent_core.config` 不会形成循环（agent_core import tools，tools import agent_core.config，config 不 import 任何业务模块，安全）。

### 8. 新建 `artifacts/` 包 — 产物检测统一模块
**What**：合并 `run.py` L182–232 与 `channels/wechat/bridge.py` L65–91 的两份产物检测实现。
**Why**：消除重复逻辑，统一 mime_map。
**How**：
```python
# artifacts/detector.py
from pathlib import Path
import mimetypes
from agent_core.config import OUTPUT_DIR

_MIME_MAP = { ... }  # 合并两份 mime_map（run.py 的 16 项 + wechat 的项）

def snapshot_output_dir() -> set[tuple[str, int]]:
    """快照 output/ 目录：返回 (relative_path, file_size) 集合。"""
    snapshot: set[tuple[str, int]] = set()
    for f in OUTPUT_DIR.rglob("*"):
        if f.is_file():
            try:
                rel = f.relative_to(OUTPUT_DIR).as_posix()
                snapshot.add((rel, f.stat().st_size))
            except OSError:
                continue
    return snapshot

def detect_new_artifacts(before: set[tuple[str, int]]) -> list[dict]:
    """对比快照，返回新增产物元数据列表。"""
    ...  # 合并 run.py 的实现（含 url="/output/{rel_path}" 字段）
```
`artifacts/__init__.py` 导出两个函数。

### 9. 新建 `entrypoints/` 包 — 入口实现
**What**：4 个入口脚本的主体移入 `entrypoints/`，根目录保留薄 shim。
**Why**：根目录整洁，启动命令兼容。
**How**（每个入口主体原样迁移，仅改 import 路径）：
- `entrypoints/web.py` ← 原 `run.py`：
  - 删除 `from agent_runtime import SYSTEM_PROMPT, backend, create_llm, render_html, research_subagent` 和 `from time_tools import get_current_time`
  - 改为 `from agent_core import build_agent, SYSTEM_PROMPT, research_subagent, create_llm`；`from sandbox import backend`；`from tools import get_current_time, render_html`
  - 删除 `run.py` 的 `build_agent()`（L107–129），直接用 `from agent_core import build_agent`
  - 产物检测改用 `from artifacts import snapshot_output_dir, detect_new_artifacts`，删除 `_snapshot_output_dir`/`_detect_new_artifacts`/`OUTPUT_DIR` 局部定义
  - `Path("workspace/uploads")`/`Path("workspace/output")` 改为 `from agent_core.config import UPLOADS_DIR, OUTPUT_DIR`
  - 保留 `if __name__ == "__main__":` → 调 `main()`；提供 `def main(): ...` 包裹 uvicorn 启动
- `entrypoints/wechat.py` ← 原 `run_wechat.py`：内容不变（已通过 channels 组装）
- `entrypoints/wecom.py` ← 原 `run_wecom.py`：内容不变
- `entrypoints/cli.py` ← 原 `demo.py`：
  - 删除自建 agent（L27–40），改 `from agent_core import build_agent`；`agent = build_agent(hitl=True)`
  - 删除 `from agent_runtime import create_llm, backend, web_search, get_current_time`
  - 改为 `from agent_core import create_llm`；`from tools import get_current_time`（web_search 不再放主 agent）
  - 保留 CLI 交互循环、多模态图片处理逻辑不变

### 10. 根级薄 shim（4 个）
**What**：`run.py`/`run_wechat.py`/`run_wecom.py`/`demo.py` 各缩为 2–3 行。
**Why**：兼容现有启动命令（`python run.py` / `python demo.py`）。
**How**（统一模式）：
```python
# run.py
from entrypoints.web import main
if __name__ == "__main__":
    main()
```
其余 3 个同理（`entrypoints.wechat.main` / `entrypoints.wecom.main` / `entrypoints.cli.main`）。每个 entrypoints 模块需提供 `main()` 函数包裹原 `if __name__ == "__main__"` 块。

### 11. `channels/` 补全 + 改 import
**What**：3 个 `__init__.py` 补内容，2 个 bridge 改 import + 产物检测。
**Why**：包级导出清晰、bridge 不再硬耦合 `agent_runtime`。
**How**：
- `channels/__init__.py`：补文档字符串 + `from channels import wechat, wecom`（按需，避免循环）
- `channels/wechat/__init__.py`：补文档字符串，导出 `WechatConfig`、`Monitor`、`Sender` 等
- `channels/wecom/__init__.py`：补文档字符串，导出 `WeComConfig`、`build_ws_client` 等
- `channels/wechat/bridge.py` L31：`from agent_runtime import agent` → `from agent_core import agent`
- `channels/wechat/bridge.py` L46–47 + L65–91：`_WORKSPACE`/`_OUTPUT_DIR`/`_snapshot`/`_diff_artifacts` 删除，改 `from artifacts import snapshot_output_dir, detect_new_artifacts`；`from agent_core.config import OUTPUT_DIR`
- `channels/wecom/bridge.py` L16：`from agent_runtime import agent` → `from agent_core import agent`
- `channels/wechat/bridge.py` 的 `_invoke_agent`（L181–211）和 `channels/wecom/bridge.py` 的 `stream_agent_reply`（L110–192）调用方式不变（仍是 `agent.astream_events`）

### 12. 新建 `tests/` + 迁移测试
**What**：`test_playwright_pdf.py` 移入 `tests/`。
**Why**：测试与生产代码分离。
**How**：移动文件，无内容改动（若其 import 了根级模块，同步更新 import 路径；经查该脚本独立运行，无项目内 import）。

### 13. 删除根级旧文件
- `agent_runtime.py`（内容已拆分到 `agent_core/` + `sandbox/`）
- `ducktools.py` / `html_tools.py` / `time_tools.py`（已移入 `tools/`）

---

## Migration & Import Updates（迁移与 import 更新总表）

| 旧 import | 新 import | 出现位置 |
|---|---|---|
| `from agent_runtime import agent` | `from agent_core import agent` | wechat/bridge.py L31, wecom/bridge.py L16 |
| `from agent_runtime import SYSTEM_PROMPT, backend, create_llm, render_html, research_subagent` | `from agent_core import build_agent, SYSTEM_PROMPT, research_subagent, create_llm` + `from sandbox import backend` + `from tools import render_html` | run.py L66–72 → entrypoints/web.py |
| `from time_tools import get_current_time` | `from tools import get_current_time` | run.py L73 → entrypoints/web.py |
| `from agent_runtime import create_llm, backend, web_search, get_current_time` | `from agent_core import build_agent, create_llm` + `from sandbox import backend` + `from tools import get_current_time` | demo.py L16 → entrypoints/cli.py |
| `from ducktools import web_search` | `from tools import web_search` | agent_runtime L30 → agent_core/prompts.py |
| `from html_tools import render_html` | `from tools import render_html` | agent_runtime L31 → agent_core/runtime.py |
| `from time_tools import get_current_time` | `from tools import get_current_time` | agent_runtime L32 → agent_core/runtime.py |

---

## Assumptions & Decisions（假设与决策）

1. **决策**：`agent_runtime.py` 完全删除，不留 re-export shim（用户选择"全面重构"，且仅要求入口脚本保留 shim）。所有 `from agent_runtime import ...` 更新到新路径。
2. **决策**：`build_agent(hitl=False)` 为唯一装配入口。`agent` 模块单例 = `build_agent(hitl=False)`，供 channels 使用。web 入口用 `build_agent(hitl=HITL_ENABLED)`，CLI 用 `build_agent(hitl=True)`。
3. **决策**：`demo.py` 的短 prompt、主 agent 含 web_search、`interrupt_on={"web_search":True}` 三项分叉统一消除（这是"统一装配"的预期结果，使 CLI 与 web/channel 一致）。HITL 统一为 `{"execute":True}`（web_search 不在主 agent，原 web_search HITL 无效）。
4. **假设**：`skills=["skills/"]` 字面量保持不变——其解析涉及 deepagents 内部语义，不在本次重构范围。
5. **假设**：`tools/render_html.py` import `agent_core.config` 不构成循环（config 不 import 业务模块）。
6. **假设**：前端 `agent-frontend/` 通过 HTTP/SSE 与后端解耦，端点契约（`/chat`、`/chat/resume`、`/upload`、`/output/{path}`、`/health`）不变，前端无需改动。
7. **决策**：`channels/` 的 channel 专属配置（`WechatConfig`/`WeComConfig`）保留在各自 `config.py`，不并入 `agent_core/config.py`（仅跨模块共享的路径/LLM/HITL 配置统一）。
8. **决策**：不创建根级 `__init__.py`（`/workspace` 是项目根而非包，子包 `agent_core/`/`sandbox/`/`tools/` 等才是包，与现有 `channels/` 模式一致）。

---

## Verification Steps（验证步骤）

### 阶段 1：静态检查
1. **包结构完整性**：确认每个新包都有 `__init__.py`：`agent_core/`、`sandbox/`、`tools/`、`artifacts/`、`entrypoints/`、`tests/`。
2. **无残留旧 import**：`grep -rn "from agent_runtime import\|from ducktools import\|from html_tools import\|from time_tools import" /workspace --include="*.py"` 应仅命中根级 shim（若有）或为空。
3. **无残留 `from agent_runtime`**：确认 `agent_runtime.py` 已删除，所有引用已迁移。

### 阶段 2：导入冒烟测试
4. `cd /workspace && python -c "import agent_core; print(agent_core.agent is not None)"` — agent 单例可构造。
5. `cd /workspace && python -c "from tools import web_search, render_html, get_current_time; print('tools ok')"` — 工具包可导入。
6. `cd /workspace && python -c "from sandbox import backend; print('sandbox ok')"` — 沙箱可导入。
7. `cd /workspace && python -c "from artifacts import snapshot_output_dir, detect_new_artifacts; print('artifacts ok')"` — 产物检测可导入。
8. `cd /workspace && python -c "from channels.wechat.bridge import handle_message; print('wechat ok')"` — channel bridge 不再因 `agent_runtime` 缺失而失败。
9. `cd /workspace && python -c "from channels.wecom.bridge import stream_agent_reply; print('wecom ok')"` — 同上。

### 阶段 3：入口冒烟测试
10. `cd /workspace && python -c "from entrypoints.web import main; print('web entry ok')"` — web 入口可加载（不启动 uvicorn）。
11. `cd /workspace && python -c "from entrypoints.cli import main; print('cli entry ok')"` — CLI 入口可加载。
12. `cd /workspace && python run.py --help`（或启动后 Ctrl+C）— 薄 shim 正常委派。
13. `cd /workspace && python demo.py`（启动后立即退出）— CLI 薄 shim 正常委派。

### 阶段 4：行为一致性验证
14. **agent 配置统一**：`python -c "from agent_core import build_agent; a=build_agent(hitl=False); b=build_agent(hitl=True); print('both ok')"` — 两种 HITL 模式均可构造。
15. **产物检测去重**：确认 `run.py`/`entrypoints/web.py` 与 `channels/wechat/bridge.py` 都调用 `artifacts.detect_new_artifacts`，无各自本地实现。
16. **前端契约不变**：启动 `python run.py`，用前端或 curl 验证 `/health`、`/chat`（SSE）、`/upload`、`/output/{path}` 端点响应格式与重构前一致（对照 `agent-frontend/src/types/domain.ts` 的 SSE 事件格式）。
17. **沙箱行为不变**：跑一个 skill 脚本（如 `md-to-pdf` 的 `render_pdf.py`）通过 agent execute，确认白名单 + 路径改写 + 编码兼容行为与重构前一致。

### 阶段 5：清理验证
18. 根目录 Python 文件仅剩：`run.py`、`run_wechat.py`、`run_wecom.py`、`demo.py`（4 个薄 shim）。`agent_runtime.py`/`ducktools.py`/`html_tools.py`/`time_tools.py`/`test_playwright_pdf.py` 已不在根。
19. `ls /workspace/*.py` 输出仅 4 个 shim 文件。
