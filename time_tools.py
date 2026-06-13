from langchain_core.tools import tool
from datetime import datetime

@tool
def get_current_time() -> str:
    """返回当前时间"""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")