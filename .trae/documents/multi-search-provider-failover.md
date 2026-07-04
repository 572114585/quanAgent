# 多搜索 Provider 接入与失败回退实施计划

## 摘要

将 Tavily、Brave Search、Serper 三个第三方搜索 API 接入项目,与现有 DuckDuckGo 形成 4 级 failover 链路。所有 provider 仅使用免费额度,API key 通过后端 `.env` 配置,运行时按 HTTP 错误码(429/402/quota_exceeded)即时切换,某 provider 触发额度错误后冷却 1 小时,三个第三方全部不可用时回退到 DuckDuckGo。

**链路顺序**: `Tavily → Brave → Serper → DuckDuckGo`

---

## 现状分析(基于 Phase 1 探索)

### 现有 DuckDuckGo 实现
- 文件: [tools/web_search.py](file:///d:/project/tools/web_search.py) 共 149 行
- 库: `from ddgs import DDGS`(requirement.txt 第 1 行)
- 入口: `@tool def web_search(query, max_results=5, topic="general") -> str`(第 109 行)
- 调用: `with DDGS() as ddgs: ddgs.text(query, max_results=...)`(第 118-124 行)
- 返回: Markdown 拼接,每条 `[标题](链接)\n摘要\n## 正文\n<抓取的网页正文>`(第 129-147 行)
- 配套: `_fetch_webpage(url)`(第 66-106 行)用 httpx 抓正文,`_is_safe_target_url(url)`(第 29-63 行)做 SSRF 防护
- 错误处理: 顶层 try/except 兜底返回中文字符串(第 148-149 行),无重试无降级

### 工具注册位置
- 主 agent tools: [agent_core/runtime.py](file:///d:/project/agent_core/runtime.py) 第 134 行 `tools=[get_current_time, render_html]`(不含 web_search)
- web_search 作为子 agent 工具: [agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) 第 24-39 行 `research_subagent["tools"] = [web_search]`,第 33 行 system_prompt 显式提到 `web_search`
- 统一导出: [tools/__init__.py](file:///d:/project/tools/__init__.py) 第 7-9 行

### 配置加载
- 后端: [agent_core/config.py](file:///d:/project/agent_core/config.py) 用 `python-dotenv` 读 env(第 13 行),现有变量有 `LLM_PROVIDER` / `AGNES_*` / `DEEPSEEK_*` / `HITL_ENABLED` 等
- 前端 Settings Store: [agent-frontend/src/stores/settings.ts](file:///d:/project/agent-frontend/src/stores/settings.ts) 字段 `apiBaseUrl`/`model`/`streamEnabled`,仅前端用,后端 `/chat` 不接收
- 设置面板: [agent-frontend/src/views/SettingsView.vue](file:///d:/project/agent-frontend/src/views/SettingsView.vue) 当前无 API key 输入框

### 现有抽象参考
- LLM 工厂: [agent_core/llm.py](file:///d:/project/agent_core/llm.py) `create_llm()` 基于 `LLM_PROVIDER` env 切换(可作多 provider 模式参考)
- 无 BaseProvider 抽象,无重试/熔断库(tenacity/stamina 均未声明)

### 关键约束
- web_search 入口签名必须保持不变(向后兼容 research_subagent system_prompt)
- `_is_safe_target_url` SSRF 防护必须复用
- 后端 `/chat` 协议不扩展(API key 走 .env,与用户决策一致)

---

## 实施步骤

### 步骤 1: 新建 `tools/search/` 包(provider 抽象层)

**新文件**: `d:\project\tools\search\__init__.py`
```python
from .base import BaseSearchProvider, SearchQuery, SearchResult, QuotaExceededError
from .tavily import TavilyProvider
from .brave import BraveProvider
from .serper import SerperProvider
from .duckduckgo import DuckDuckGoProvider
from .registry import get_search_results

__all__ = [
    "BaseSearchProvider", "SearchQuery", "SearchResult", "QuotaExceededError",
    "TavilyProvider", "BraveProvider", "SerperProvider", "DuckDuckGoProvider",
    "get_search_results",
]
```

**新文件**: `d:\project\tools\search\base.py`
- 定义数据类:
  - `SearchQuery`: 字段 `query: str` / `max_results: int = 5` / `topic: str = "general"`
  - `SearchResult`: 字段 `title: str` / `url: str` / `snippet: str` / `content: str = ""`(可选正文)
- 定义 `QuotaExceededError(Exception)`:provider 额度耗尽时抛出,registry 据此切换
- 定义 `BaseSearchProvider` 抽象基类(ABC):
  - `__init__(self, api_key: str)` 保存 key,`self.name` 子类设置
  - 抽象方法 `async def search(self, query: SearchQuery) -> list[SearchResult]`
  - 抽象方法 `def is_available(self) -> bool`:检查 key 是否配置 + 是否在冷却期
  - 内部 `self._cooldown_until: float = 0.0`
  - `def mark_cooldown(self, seconds: int = 3600)`:设置冷却到期时间
  - `def _is_in_cooldown(self) -> bool`:`time.time() < self._cooldown_until`

**新文件**: `d:\project\tools\search\tavily.py`
- `class TavilyProvider(BaseSearchProvider)`,`name = "tavily"`
- `is_available()`: api_key 非空 且 不在冷却期
- `search()` 实现:
  - 用 `httpx.AsyncClient` POST `https://api.tavily.com/search`(不引入 tavily-python SDK,减少依赖)
  - body: `{"query": q.query, "max_results": q.max_results, "search_depth": "basic", "topic": q.topic, "include_answer": False, "include_raw_content": False}`
  - header: `Authorization: Bearer {api_key}`
  - 超时 10 秒
  - 错误码识别:
    - HTTP 429 / 402 → 抛 `QuotaExceededError`
    - 响应 JSON 含 `"error"` 字段且消息含 `quota`/`limit`/`credits` → 抛 `QuotaExceededError`
  - 成功: 解析 `data["results"]`,映射到 `SearchResult(title/url/content→snippet)`
- **免费额度**: 1k 次/月,无需本地计数,靠 429 触发冷却

**新文件**: `d:\project\tools\search\brave.py`
- `class BraveProvider(BaseSearchProvider)`,`name = "brave"`
- `search()` 实现:
  - GET `https://api.search.brave.com/res/v1/web/search`
  - header: `X-Subscription-Token: {api_key}` + `Accept: application/json`
  - params: `q={query}` / `count={max_results}`
  - 超时 10 秒
  - 错误码识别:
    - HTTP 429 → 抛 `QuotaExceededError`
    - HTTP 402 Payment Required → 抛 `QuotaExceededError`
  - 成功: 解析 `data["web"]["results"]`,映射到 `SearchResult(title/url/description→snippet)`
- **免费额度**: $5 credits/月,靠 429/402 触发冷却

**新文件**: `d:\project\tools\search\serper.py`
- `class SerperProvider(BaseSearchProvider)`,`name = "serper"`
- `search()` 实现:
  - POST `https://google.serper.dev/search`
  - header: `X-API-KEY: {api_key}` + `Content-Type: application/json`
  - body: `{"q": query, "num": max_results}`
  - 超时 10 秒
  - 错误码识别:
    - HTTP 429 → 抛 `QuotaExceededError`
    - HTTP 402 → 抛 `QuotaExceededError`
    - 响应含 `"error"` 且含 `credits`/`quota` → 抛 `QuotaExceededError`
  - 成功: 解析 `data["organic"]`,映射到 `SearchResult(title/link→url/snippet)`
- **免费额度**: 2500 次一次性,靠 429/402 触发冷却

**新文件**: `d:\project\tools\search\duckduckgo.py`
- `class DuckDuckGoProvider(BaseSearchProvider)`,`name = "duckduckgo"`
- `__init__` 不需要 api_key 参数(或接收 None)
- `is_available()`: 永远 True(兜底,不受冷却影响)
- `search()` 实现:
  - 迁移现有 web_search.py 第 117-124 行的 DDGS 调用逻辑
  - `from ddgs import DDGS` 在本文件内导入
  - `with DDGS() as ddgs: results = list(ddgs.text/news(...))`
  - 同步调用(DDGS 库本身同步),用 `asyncio.get_event_loop().run_in_executor(None, ...)` 包一层避免阻塞事件循环
  - 映射到 `SearchResult`(title/href→url/body→snippet)
  - DDG 不抛 `QuotaExceededError`(它是兜底,失败就抛普通 Exception)
- 注意: DDG provider 不做网页正文抓取,正文抓取统一在 web_search 入口层做(见步骤 2)

**新文件**: `d:\project\tools\search\registry.py`
- 模块级状态: `_providers: list[BaseSearchProvider]` 按顺序初始化一次(单例)
- `def _init_providers() -> list[BaseSearchProvider]`:
  - 读 config.py 暴露的 4 个 key
  - 按固定顺序构造: `[TavilyProvider(key) if key else None, BraveProvider(key) if key else None, SerperProvider(key) if key else None, DuckDuckGoProvider()]`
  - 过滤掉 None(Tavily/Brave/Serper 无 key 时跳过,不入链路)
- `async def get_search_results(query: SearchQuery) -> tuple[list[SearchResult], str]`:
  - 返回 `(results, used_provider_name)`
  - 遍历 `_providers`:
    - 跳过 `not provider.is_available()` 的
    - try: `results = await provider.search(query)`;若非空直接返回
    - except `QuotaExceededError`: `provider.mark_cooldown(3600)`;记 log;continue
    - except 其他 Exception: 记 warning log;continue(不冷却,可能是网络抖动)
  - 全部失败:最后尝试 `DuckDuckGoProvider`(若不在 _providers 里则新建一个)
  - DuckDuckGo 也失败 → 抛 `RuntimeError("所有搜索 provider 均不可用")`
- 线程安全:用 `asyncio.Lock` 保护 `_providers` 初始化(懒加载)

### 步骤 2: 改造 `tools/web_search.py`

**修改文件**: [tools/web_search.py](file:///d:/project/tools/web_search.py)

保留:
- `_MAX_CONTENT_CHARS` / `_FETCH_TIMEOUT` / `_FETCH_TOP_N` / `_MAX_FETCH_BYTES` 常量(第 20-26 行)
- `_is_safe_target_url(url)` SSRF 防护(第 29-63 行)— 任何 provider 抓正文都复用
- `_fetch_webpage(url)` 网页抓取(第 66-106 行)
- `@tool def web_search(query, max_results=5, topic="general") -> str` 签名不变(第 109 行)— 保证 research_subagent system_prompt 不用改

替换 web_search 函数体(第 110-149 行):
```python
@tool
def web_search(query: str, max_results: int = 5, topic: str = "general") -> str:
    """搜索网络获取最新信息..."""  # 保留原 docstring
    import asyncio
    from tools.search import get_search_results, SearchQuery

    async def _run():
        sq = SearchQuery(query=query, max_results=max_results, topic=topic)
        results, provider_name = await get_search_results(sq)
        # 组装 Markdown 输出(沿用原格式)
        lines = [f"[搜索来源: {provider_name}]"]
        # 对前 _FETCH_TOP_N 个结果抓正文(复用 _fetch_webpage)
        for i, r in enumerate(results[:_FETCH_TOP_N]):
            content = _fetch_webpage(r.url) if _is_safe_target_url(r.url) else ""
            entry = f"\n## [{r.title}]({r.url})\n\n{r.snippet}\n"
            if content:
                entry += f"\n## 正文\n{content[:_MAX_CONTENT_CHARS]}\n"
            lines.append(entry)
        # 剩余结果只展示 snippet
        for r in results[_FETCH_TOP_N:]:
            lines.append(f"\n## [{r.title}]({r.url})\n\n{r.snippet}\n")
        return "\n---\n".join(lines)

    try:
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # 已在事件循环中(如 FastAPI),用 ensure_future
                import asyncio as _a
                fut = _a.ensure_future(_run())
                return _a.get_event_loop().run_until_complete(_a.wait([fut]))[0].result()
        except RuntimeError:
            pass
        return asyncio.run(_run())
    except Exception as e:
        return f"搜索时出错：{str(e)}"
```

**注意**: web_search 是同步 `@tool`,但 LangChain 的 `astream` 会在线程池里调用它。为简化,可以用 `asyncio.run()`(因为是在独立线程,没有事件循环冲突)。如果运行时报 "event loop already running",改用 `asyncio.run_coroutine_threadsafe` 模式。具体实现时优先用最简单的 `asyncio.run(_run())`,验证通过即可。

### 步骤 3: 修改 `agent_core/config.py`

**修改文件**: [agent_core/config.py](file:///d:/project/agent_core/config.py)

在第 30 行后追加(开关区之后):
```python
# ===== 搜索 Provider 配置 =====
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")
BRAVE_API_KEY: str = os.getenv("BRAVE_API_KEY", "")
SERPER_API_KEY: str = os.getenv("SERPER_API_KEY", "")
# provider 冷却时间(秒),额度耗尽后多久再重试
SEARCH_PROVIDER_COOLDOWN_SECONDS: int = int(os.getenv("SEARCH_PROVIDER_COOLDOWN_SECONDS", "3600"))
```

### 步骤 4: 修改 `requirement.txt`

**修改文件**: [requirement.txt](file:///d:/project/requirement.txt)

确认 `ddgs` 已在(第 1 行)。`httpx` 通常已被 FastAPI 间接依赖,但显式声明更稳妥。追加:
```
httpx>=0.27.0
```
(Tavily/Brave/Serper 全部用 httpx 调用,不引入任何专用 SDK,保持依赖最小)

### 步骤 5: 新建 `.env.example` 示例(可选但推荐)

**新文件**: `d:\project\.env.example`
```
# 复制为 .env 并填写你的 key。任一留空则该 provider 不启用,自动跳过。
TAVILY_API_KEY=
BRAVE_API_KEY=
SERPER_API_KEY=
SEARCH_PROVIDER_COOLDOWN_SECONDS=3600
```
(不创建真实 .env,用户自己填;`.env.example` 可提交 git 作文档)

---

## 假设与决策

### 决策(已与用户确认)
1. **API key 存储位置**: 后端 `.env` 文件,通过 `os.getenv` 读取。不改前端 settings.ts,不扩展 /chat 协议。
2. **额度判定方式**: 按 HTTP 错误码(429/402/quota_exceeded)即时切换,触发后冷却 1 小时。不做本地月度计数(各家计费维度不同,容易算不准)。

### 设计决策(实现时按此执行,无需再问)
1. **链路顺序固定**: `Tavily → Brave → Serper → DuckDuckGo`。顺序硬编码在 registry.py,不开放配置(用户要"三个都接进来"且"用完一个用下一个",顺序明确)。
2. **provider 无 key 时跳过**: `.env` 里某 key 留空,该 provider 直接不进 `_providers` 链路(不是"失败"而是"未配置")。
3. **DuckDuckGo 永远在链路末尾**: 作为兜底,不受冷却影响,不抛 QuotaExceededError。
4. **web_search 入口签名不变**: `(query, max_results, topic) -> str`,返回 Markdown 字符串。保证 [agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) 第 33 行的 system_prompt 不用改。
5. **正文抓取保留在 web_search 入口层**: 各 provider 只返回 `SearchResult`(标题/url/snippet),正文抓取统一由 web_search 复用 `_fetch_webpage` 完成。这样:
   - Tavily 的 `include_raw_content` 设为 False(省额度,自己抓)
   - Brave/Serper 本来就没有正文,自己抓
   - SSRF 防护统一在 web_search 层
6. **不引入专用 SDK**: Tavily/Brave/Serper 全部用 `httpx` 直接调 REST,减少依赖。`tavily-python` 不引入。
7. **错误码识别口径**:
   - Tavily: HTTP 429/402,或 JSON `error` 字段含 quota/limit/credits
   - Brave: HTTP 429/402
   - Serper: HTTP 429/402,或 JSON `error` 含 credits/quota
   - DDG: 不识别额度错误(它是兜底)
8. **冷却时间默认 1 小时**: 可通过 `SEARCH_PROVIDER_COOLDOWN_SECONDS` env 调整。
9. **并发安全**: registry 的 `_providers` 用懒加载 + `asyncio.Lock` 保护初始化,运行时只读。
10. **日志**: 用现有 logging 配置(web.py 顶部有 logger),provider 切换、冷却、失败都记 warning/info log,方便排查。

### 假设
- LangChain `@tool` 同步函数内调用异步代码的兼容性:用 `asyncio.run()` 在独立线程执行(因为 LangChain 工具在线程池里跑,没有冲突的事件循环)。若验证失败,改用 `asyncio.run_coroutine_threadsafe`。这是实现期需要验证的点,不影响整体架构。
- 各家 API endpoint 和认证方式基于本次调研的官方文档(Tavily Bearer token、Brave X-Subscription-Token、Serper X-API-KEY)。
- 免费额度足够日常使用,不需要本地配额管理。

---

## 验证步骤

### 1. 静态检查
- `python -c "from tools.search import TavilyProvider, BraveProvider, SerperProvider, DuckDuckGoProvider, get_search_results"` 无报错
- `python -c "from tools import web_search; print(web_search.name)"` 输出 `web_search`
- `python -c "from agent_core.config import TAVILY_API_KEY, BRAVE_API_KEY, SERPER_API_KEY; print('OK')"` 无报错

### 2. 单 provider 单元测试(在 tests/ 下新增 `test_search_providers.py`)
- Mock httpx 响应,验证每个 provider 的错误码识别:
  - 429 → 抛 QuotaExceededError
  - 402 → 抛 QuotaExceededError
  - 200 + 正常 results → 返回 list[SearchResult]
- 验证 `mark_cooldown` 后 `is_available()` 返回 False,冷却到期后返回 True

### 3. failover 链路测试
- 构造 3 个 mock provider,前两个抛 QuotaExceededError,第三个正常
- 验证 `get_search_results` 返回第三个的结果,且 `used_provider_name` 正确
- 验证前两个被标记冷却
- 构造全部第三方失败场景,验证 DDG 兜底被调用

### 4. 端到端手动测试
- `.env` 填入错误的 Tavily key(故意触发 401/402),正确的 Brave key
- 启动后端,在前端发"搜一下今天的新闻"
- 查看后端 log:应看到 "tavily 不可用,切换到 brave"
- 验证返回结果正常(来自 Brave)
- 把 Brave key 也改错,验证回退到 Serper
- 把三个都改错,验证回退到 DuckDuckGo

### 5. 回归测试
- 验证 research_subagent 的 system_prompt 无需修改(web_search 签名未变)
- 验证 SSE 流式输出正常(tool_call / tool_result 事件格式未变)
- 验证 `_fetch_webpage` 和 `_is_safe_target_url` 行为未变

---

## 文件清单总览

### 新建文件(7 个)
1. `d:\project\tools\search\__init__.py`
2. `d:\project\tools\search\base.py`
3. `d:\project\tools\search\tavily.py`
4. `d:\project\tools\search\brave.py`
5. `d:\project\tools\search\serper.py`
6. `d:\project\tools\search\duckduckgo.py`
7. `d:\project\tools\search\registry.py`
8. `d:\project\.env.example`(可选文档)
9. `d:\project\tests\test_search_providers.py`(可选测试)

### 修改文件(3 个)
1. [tools/web_search.py](file:///d:/project/tools/web_search.py) — 替换 web_search 函数体,保留 _fetch_webpage / _is_safe_target_url / 常量
2. [agent_core/config.py](file:///d:/project/agent_core/config.py) — 追加 4 个 env 变量读取
3. [requirement.txt](file:///d:/project/requirement.txt) — 追加 httpx 显式声明

### 不修改的文件(显式声明,避免误改)
- [agent_core/runtime.py](file:///d:/project/agent_core/runtime.py) — build_agent 工具列表不变
- [agent_core/prompts.py](file:///d:/project/agent_core/prompts.py) — research_subagent 不变(web_search 签名未变)
- [tools/__init__.py](file:///d:/project/tools/__init__.py) — web_search 导出不变
- [entrypoints/web.py](file:///d:/project/entrypoints/web.py) — SSE 流处理不变
- [agent-frontend/](file:///d:/project/agent-frontend) — 前端完全不动(API key 走 .env)
