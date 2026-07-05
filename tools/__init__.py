"""扁平工具包：统一导出所有 LangChain @tool 工具。

原 ducktools.py / html_tools.py / time_tools.py 散落在项目根目录，导入路径
不统一（有的从 agent_runtime re-export，有的直接 import）。现统一收敛到
tools/ 包，所有调用方 `from tools import web_search, render_html, get_current_time`。
"""
# 注意 import 顺序:kb_tool 不依赖 agent_core,放最前。
# 若 render_html 放前面,会触发 agent_core → build_agent → prompts → from tools.kb_tool import kb_search,
# 此时 tools.kb_tool 模块尚未加载(卡在 tools/__init__.py 的 render_html 行),
# Python 返回部分初始化的模块对象,kb_search 名字绑到 module 而非函数,导致 @tool 报错。
from tools.kb_tool import kb_search, kb_add_document
from tools.web_search import web_search
from tools.render_html import render_html
from tools.get_current_time import get_current_time

__all__ = ["web_search", "render_html", "get_current_time", "kb_search", "kb_add_document"]
