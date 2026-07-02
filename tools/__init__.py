"""扁平工具包：统一导出所有 LangChain @tool 工具。

原 ducktools.py / html_tools.py / time_tools.py 散落在项目根目录，导入路径
不统一（有的从 agent_runtime re-export，有的直接 import）。现统一收敛到
tools/ 包，所有调用方 `from tools import web_search, render_html, get_current_time`。
"""
from tools.web_search import web_search
from tools.render_html import render_html
from tools.get_current_time import get_current_time

__all__ = ["web_search", "render_html", "get_current_time"]
